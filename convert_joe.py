#! /usr/bin/env python

# By Fedor Iskhakov
# fedor.iskh.me

# The packages:
# geopy is needed for geo-locating the employers
# bleach is needed for cleaning up the content of ads for Evernote standard (ENML)
# https://dev.evernote.com/doc/articles/enml.php#prohibited
# https://pypi.python.org/pypi/bleach
# http://geopy.readthedocs.org/en/1.10.0/

import sys
import xml.etree.ElementTree as ET
import geopy
import datetime
import calendar
import bleach
from xml.sax.saxutils import escape

# SETUP:
# The XML file downloaded from JOE
joe_xmlfile='<PATH>'
# The output file that will be imported into Evernote
evernote_xmlfile='<PATH>'

print '''
 Python script that converts XML positions data downloaded from JOE (joe_full_xml.xml)
 to ENEX format XML that can be imported into Evernote.
 '''

#patch for CDATA support from http://www.kaarsemaker.net/blog/2013/10/10/cdata-support-in-elementtree/
def CDATA(text=None):
    element = ET.Element('![CDATA[')
    element.text = text
    return element

# Python 2.7 and 3
if hasattr(ET, '_serialize_xml'):
    ET._original_serialize_xml = ET._serialize_xml
    def _serialize_xml(write, elem, *args):
        if elem.tag == '![CDATA[':
            # write("%s%s" % (elem.tag, elem.text))
            write("<![CDATA[%s]]>" % elem.text.encode('utf-8'))
            return
        return ET._original_serialize_xml(write, elem, *args)
    ET._serialize_xml = ET._serialize['xml'] = _serialize_xml
# Python 2.5-2.6, and non-stdlib ElementTree
elif hasattr(ET.ElementTree, '_write'):
    ET.ElementTree._orig_write = ET.ElementTree._write
    def _write(self, file, node, encoding, namespaces):
        if node.tag == '![CDATA[':
            file.write("\n<![CDATA[%s]]>\n" % node.text.encode(encoding))
        else:
            self._orig_write(file, node, encoding, namespaces)
    ET.ElementTree._write = _write
else:
    raise RuntimeError("Don't know how to monkeypatch CDATA support. Please report a bug at https://github.com/seveas/python-hpilo")


from geopy.geocoders import Nominatim
# from geopy.geocoders import GoogleV3
geolocator = Nominatim()
# geolocator = GoogleV3()

# input XML tree
intree = ET.parse(joe_xmlfile)
# output start building the tree
root2 = ET.Element("en-export")

#number of positions in the file
npos=len(list(intree.iter('position')))
i=1

yeartag=intree.find('year')
year=yeartag.attrib['joe_year_ID']
issue=yeartag.find('issue').attrib['joe_issue_ID']
if len(issue)==1:
	issue='0'+issue

for position in intree.iter('position'):
	print '\nPosition ',i,' of ',npos,':'
	joeid=year+'-'+issue+'_'+position.attrib['jp_id']
	print '      JOE id=',joeid
	section = position.find('jp_section').text
	print '     section=',section
	title=position.find('jp_title').text
	print '       title=',title
	institution=position.find('jp_institution').text
	print ' institution=',institution
	print '     address=',
	sys.stdout.flush()

	#analyse location
	try:
		loc=position.find('locations').find('location')
		country=loc.find('country').text
		if country is None:
			country=''
		state=loc.find('state').text
		if state is None:
			state=''
		city=loc.find('city').text
		if city is None:
			city=''
		geo = geolocator.geocode(' '.join([institution,city,state,country]), exactly_one=True)
		if geo is None:
			geo = geolocator.geocode(' '.join([city,state,country]), exactly_one=True)
			if geo is None:
				geo = geolocator.geocode(institution, exactly_one=True)
	except Exception: 
		geo = None

	if geo is not None:
		print geo.address,
		print((geo.latitude, geo.longitude))
	else:
		print 'unknown after 3'

	i=i+1

	# JEL codes and keywords
	jel=position.find('JEL_Classifications')
	jel_codes=list(jel.iter('jc_description'))
	keywords=position.find('jp_keywords').text
	if keywords is not None:
		keywords=keywords.split("\n")

	#start creating a note for Evernote
	note = ET.SubElement(root2, "note")
	ET.SubElement(note, "title").text = title+' at '+institution
	if 'full-time' in section.lower():
		ET.SubElement(note, "tag").text = 'Full-Time'
	if 'nonacademic' in section.lower():
		ET.SubElement(note, "tag").text = 'Non-Academic'
	if 'international' not in section.lower():
		ET.SubElement(note, "tag").text = 'USA'

	#the actual Note content	
	entry='<?xml version="1.0" encoding="UTF-8" standalone="no"?>' + \
	'<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">' + \
	'<en-note style="word-wrap: break-word; -webkit-nbsp-mode: space; -webkit-line-break: after-white-space;">'
	entry=entry+'<div style="margin-bottom:1em;"><a style="color:black" href="https://www.aeaweb.org/joe/listing.php?JOE_ID='+joeid+'">JOE id '+joeid+' (view online)</a></div>'
	entry=entry+'<div style="font-size:small;">' + section + '</div>'
	entry=entry+'<div style="font-size:large;color:#00b300">'+position.find('jp_title').text+'</div>'
	entry=entry+'<div style="font-size:large;font-weight:bold;color:#c80000">'+escape(institution)+'</div>'
	if position.find('jp_division') is not None and position.find('jp_division').text is not None:
		entry=entry+'<div style="font-size:norlam;font-weight:bold;color:#c80000">'+escape(position.find('jp_division').text)+'</div>'
	if position.find('jp_department') is not None and position.find('jp_department').text is not None:
		entry=entry+'<div style="font-size:norlam;font-weight:bold;color:#c80000">'+escape(position.find('jp_department').text)+'</div>'

	if geo is not None:
		entry=entry+'<div><a style="font-size:large;font-weight:bold;color:#0000cc" href="https://www.google.com.au/maps/@'+str(geo.latitude)+','+str(geo.longitude)+',10z">'
		check=False
		if len(city)>0:
			entry=entry+escape(city)
			check=True
		if len(state)>0:
			if check:
				entry=entry+', '
			entry=entry+escape(state)
			check=True
		if len(country)>0:
			if check:
				entry=entry+', '
			entry=entry+escape(country)
		entry=entry+'</a></div>'
	
	if position.find('jp_application_deadline') is not None and position.find('jp_application_deadline').text is not None:
		datevar=datetime.datetime.strptime(position.find('jp_application_deadline').text,"%Y-%m-%d %H:%M:%S")
		entry=entry+'<div style="font-size:large;font-weight:bold;color:#b30059">DEADLINE: '+datevar.strftime("%B %d")+'</div>'

	if jel_codes is not None:
		entry=entry+'<div style="margin-top:1.5em;margin-bottom:0em;font-size:small">Research fields:</div>'
		entry=entry+'<ul>'
		for k in jel_codes:
			entry=entry+'<li style="color:black">'+escape(k.text)+'</li>'
		entry=entry+'</ul>'

	if keywords is not None:
		entry=entry+'<div style="margin-top:1.5em;margin-bottom:0em;font-size:small">Keywords:</div>'
		entry=entry+'<ul>'
		for k in keywords:
			entry=entry+'<li style="color:black">'+escape(k)+'</li>'
		entry=entry+'</ul>'


	#clean the ad text
	allowed_tags=['a','abbr','acronym','address','area','b','bdo','big','blockquote','br','caption','center','cite','code','col','colgroup','dd','del','dfn','div','dl','dt','em','font','h1','h2','h3','h4','h5','h6','hr','i','img','ins','kbd','li','map','ol','p','pre','q','s','samp','small','span','strike','strong','sub','sup','table','tbody','td','tfoot','th','thead','title','tr','tt','u','ul','var','xmp']
	allowed_attrib=['style','href']
	allowed_styles=['font-size','font-weight','margin-bottom','margin-top','color','white-space','word-wrap']
	ad_clean=bleach.clean(position.find('jp_full_text').text,allowed_tags,allowed_attrib,allowed_styles, strip=True,strip_comments=True)

	entry=entry+'<pre style="white-space:pre-wrap;word-wrap:break-word;">'+escape(ad_clean)+'</pre>'

	entry=entry + \
	'</en-note>'

	contenttag=ET.SubElement(note, "content")
	ET.SubElement(contenttag, "![CDATA[").text=entry

	# xmlstr = ElementTree.tostring(ET, encoding='utf8', method='xml')

	note_attr=ET.SubElement(note, "note-attributes")
	note_attr.text=''
	ET.SubElement(note_attr, "author").text = 'JOE'

	if geo is not None:
		ET.SubElement(note_attr, "latitude").text = str(geo.latitude)
		ET.SubElement(note_attr, "longitude").text = str(geo.longitude)
		ET.SubElement(note_attr, "altitude").text = '0'

	#reminder and reminder order from 
	if position.find('jp_application_deadline') is not None and position.find('jp_application_deadline').text is not None:
		datevar=datetime.datetime.strptime(position.find('jp_application_deadline').text,"%Y-%m-%d %H:%M:%S")
		year_corr=max(min(datevar.year,datetime.date.today().year+1),datetime.date.today().year)
		try:
			datevar=datetime.date(year_corr,datevar.month,datevar.day)
		except ValueError: 
			#February 29 in a wrong year..
			datevar=datetime.date(year_corr,datevar.month,datevar.day-1)
		ET.SubElement(note_attr, "reminder-order").text = str(calendar.timegm(datevar.timetuple()))
		ET.SubElement(note_attr, "reminder-time").text = datevar.strftime("%Y%m%dT%H%M%SZ")

	#clean the objects
	note_attr=None
	note=None

with open(evernote_xmlfile, 'w') as f:
    f.write('<?xml version="1.0" encoding="UTF-8" ?>\n<!DOCTYPE en-export SYSTEM "http://xml.evernote.com/pub/evernote-export3.dtd">\n')
    ET.ElementTree(root2).write(f,'utf-8')



