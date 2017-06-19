#!/usr/bin/env python
"""Web server for the Trendy Lights application.

The overall architecture looks like:

               server.py         script.js
 ______       ____________       _________
|      |     |            |     |         |
|  EE  | <-> | App Engine | <-> | Browser |
|______|     |____________|     |_________|
     \                               /
      '- - - - - - - - - - - - - - -'

The code in this file runs on App Engine. It's called when the user loads the
web page and when details about a polygon are requested.

Our App Engine code does most of the communication with EE. It uses the
EE Python library and the service account specified in config.py. The
exception is that when the browser loads map tiles it talks directly with EE.

The basic flows are:

1. Initial page load

When the user first loads the application in their browser, their request is
routed to the get() function in the MainHandler class by the framework we're
using, webapp2.

The get() function sends back the main web page (from index.html) along
with information the browser needs to render an Earth Engine map and
the IDs of the polygons to show on the map. This information is injected
into the index.html template through a templating engine called Jinja2,
which puts information from the Python context into the HTML for the user's
browser to receive.

Note: The polygon IDs are determined by looking at the static/polygons
folder. To add support for another polygon, just add another GeoJSON file to
that folder.

2. Getting details about a polygon

When the user clicks on a polygon, our JavaScript code (in static/script.js)
running in their browser sends a request to our backend. webapp2 routes this
request to the get() method in the DetailsHandler.

This method checks to see if the details for this polygon are cached. If
yes, it returns them right away. If no, we generate a Wikipedia URL and use
Earth Engine to compute the brightness trend for the region. We then store
these results in a cache and return the result.

Note: The brightness trend is a list of points for the chart drawn by the
Google Visualization API in a time series e.g. [[x1, y1], [x2, y2], ...].

Note: memcache, the cache we are using, is a service provided by App Engine
that temporarily stores small values in memory. Using it allows us to avoid
needlessly requesting the same data from Earth Engine over and over again,
which in turn helps us avoid exceeding our quota and respond to user
requests more quickly.

"""

import json
import os

import config
import ee
import jinja2
import webapp2

from google.appengine.api import memcache

import urllib

###############################################################################
#                             Web request handlers.                           #
###############################################################################


class MainHandler(webapp2.RequestHandler):
  """A servlet to handle requests to load the main Trendy Lights web page."""
  def get(self):
    template_values = {
      'items': full_wh_index()
    }
    template = JINJA2_ENVIRONMENT.get_template('ys.html')
    self.response.out.write(template.render(template_values))


class DetailsHandler(webapp2.RequestHandler):
  """A servlet to handle requests for details about a Polygon."""

  def get(self):
    """Returns details about a polygon."""
    wdpaid = self.request.get('wdpaid')
    content = Calculate_water(wdpaid)
    self.response.headers['Content-Type'] = 'application/json'
    self.response.out.write(content)

class SiteHandler(webapp2.RequestHandler):
  def get(self):
    mapid = get_mapid()
    wdpaid = self.request.get('wdpaid')

    template_values = {
        'eeMapId': mapid['mapid'],
        'eeToken': mapid['token'],
        'wdpaid': wdpaid
    }

    template = JINJA2_ENVIRONMENT.get_template('site.html')
    self.response.out.write(template.render(template_values))


class FeatureHandler(webapp2.RequestHandler):
  """A servlet to handle requests for details about a Polygon."""

  def get(self):
    """Returns details about a polygon."""
    wdpaid = self.request.get('wdpaid')
    content = Get_feature(wdpaid)
    self.response.headers['Content-Type'] = 'application/json'
    self.response.out.write(content)


class SearchPaHandler(webapp2.RequestHandler):
  """A servlet to handle requests for details about a Polygon."""

  def get(self):
    """Returns details about a polygon."""
    items = self.request.get('page')
    result = Search_pa(items)
    template_values = {
      'items': result
    }

    template = JINJA2_ENVIRONMENT.get_template('pa.html')
    self.response.out.write(template.render(template_values))


app = webapp2.WSGIApplication([
    ('/site', SiteHandler),
    ('/search', SearchPaHandler),
    ('/getfeature', FeatureHandler),
    ('/details', DetailsHandler),
    ('/', MainHandler),
], debug=True)

###############################################################################
#                               Helpers                               #
###############################################################################

ppapi_token = '4290b88825725a4d241c485d3b0b7cd7'

def get_mapid():
  gsw = ee.Image('JRC/GSW1_0/GlobalSurfaceWater')
  return gsw.select('transition').getMapId()

def get_feature(wdpaid, token=ppapi_token):
  url = "https://api.protectedplanet.net/v3/protected_areas/{}?token={}&with_geometry=1".format(wdpaid, token)
  response = urllib.urlopen(url)
  data = json.loads(response.read())
  data = data['protected_area']
  # geom
  geom = data['geojson']['geometry']
  # attrs
  data.pop('geojson')
  return ee.Feature(geom, data)

def lookup_transition_code():
  lookup_names = memcache.get('lookup')

  if lookup_names is None:
    # get lookup 0 for 'No change'
    gsw = ee.Image('JRC/GSW1_0/GlobalSurfaceWater')
    lookup_names = zip(ee.List(gsw.get('transition_class_values')).getInfo(), gsw.get('transition_class_names').getInfo())
    lookup_names = dict(lookup_names)

    # push to memcache
    memcache.add('lookup', lookup_names, MEMCACHE_EXPIRATION)

  return lookup_names

def color_code():
  lookup_colors = memcache.get('color')

  if lookup_colors is None:
    # get lookup 0 for 'No change'
    gsw = ee.Image('JRC/GSW1_0/GlobalSurfaceWater')
    lookup_colors = zip(gsw.get('transition_class_values').getInfo(), gsw.get('transition_class_palette').getInfo())
    lookup_colors = dict(lookup_colors)

    # push to memcache
    memcache.add('color', lookup_colors, MEMCACHE_EXPIRATION)

  return lookup_colors

def Search_pa(page, token=ppapi_token):
  # china for the time being. At least one condition needed
  url = "https://api.protectedplanet.net/v3/protected_areas/search?designation=17&page={}&token={}".format(page, token)
  response = urllib.urlopen(url)
  data = json.loads(response.read())
  data = data['protected_areas']

  result = [{'name': each['name'], 'wdpaid':each['wdpa_id']} for each in data]
  return result

def full_wh_index():
  result = list()

  for i in range(4):
    result.extend(Search_pa(i+1))
  return result

def Get_feature(wdpaid):
  return json.dumps(get_feature(wdpaid).getInfo())

def Calculate_water(wdpaid):
  result = memcache.get(wdpaid)

  # If we've cached details for this polygon, return them.
  if result is not None:
    return result

  else:
    my_scale = 150
    gsw = ee.Image('JRC/GSW1_0/GlobalSurfaceWater')
    transition = gsw.select('transition')

    lookup_names = zip(ee.List(gsw.get('transition_class_values')).getInfo(), gsw.get('transition_class_names').getInfo())

    fc = ee.FeatureCollection(ee.List([get_feature(wdpaid)]))
    surwater = ee.Image.pixelArea().addBands(transition)
    sums = surwater.reduceRegions(
      scale=my_scale,
      collection=fc,
      reducer=ee.Reducer.sum().group(groupField=1, groupName='transition_class_value')
    )

    stats = ee.List(sums.first().get('groups')).getInfo()
    
    # lookup code for legend
    transition_lookup = lookup_transition_code()
    color_lookup = color_code()

    stats = map(lambda x: [transition_lookup[x['transition_class_value']], x['sum']/1000000, color_lookup[x['transition_class_value']]], stats)
    result = json.dumps(stats)

    # push result to avoid duplicate analysis
    memcache.add(wdpaid, result, MEMCACHE_EXPIRATION)

    return result

###############################################################################
#                               Initialization.                               #
###############################################################################
# Use our App Engine service account's credentials.
EE_CREDENTIALS = ee.ServiceAccountCredentials(
    config.EE_ACCOUNT, config.EE_PRIVATE_KEY_FILE)

# 24 hours after they are added. See:
# https://cloud.google.com/appengine/docs/python/memcache/
MEMCACHE_EXPIRATION = 60 * 60 * 24 * 3 # three days

# Create the Jinja templating system we use to dynamically generate HTML. See:
# http://jinja.pocoo.org/docs/dev/
JINJA2_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    autoescape=True,
    extensions=['jinja2.ext.autoescape'])

# Initialize the EE API.
ee.Initialize(EE_CREDENTIALS)
