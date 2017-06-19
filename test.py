# Import the Earth Engine Python Package
import ee
import urllib, json

# Initialize the Earth Engine object, using the authentication credentials.
ee.Initialize()

# analysis scale
my_scale = 150;

# load data
ppapi_token = '4290b88825725a4d241c485d3b0b7cd7'

gsw = ee.Image('JRC/GSW1_0/GlobalSurfaceWater')
transition = gsw.select('transition')

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

def calculate_water(wdpaid):
  fc = ee.FeatureCollection(ee.List([get_feature(wdpaid)]))
  surwater = ee.Image.pixelArea().addBands(transition)
  sums = surwater.reduceRegions(
    scale=my_scale,
    collection=fc,
    reducer=ee.Reducer.sum().group(groupField=1, groupName='transition_class_value')
  )

  stats = sums.first().get('groups').getInfo()
  return stats, json.dumps(stats)

# // Create a dictionary for looking up names of transition classes.
lookup_names = zip(ee.List(gsw.get('transition_class_values')).getInfo(), 
	gsw.get('transition_class_names').getInfo())


transition = gsw.select('transition')
surwater2 = ee.Image.pixelArea().addBands(transition)


# stats = map(lambda x: {transition_lookup[x['transition_class_value']]: x['sum']/1000000}, stats)

(c,d) = gsw.get('transition_class_values').getInfo(), gsw.get('transition_class_palette').getInfo()
# transition_fc = ee.FeatureCollection(stats.map(createFeature));
# // print('transition_fc', transition_fc);

# transition_summary_chart = ui.Chart.feature.byFeature({
#     features: transition_fc,
#     xProperty: 'transition_class_name',
#     yProperties: ['area_m2', 'transition_class_number']
#   })
#   .setChartType('PieChart')
#   .setOptions({
#     title: 'Summary of transition class areas',
#     slices: createPieChartSliceDictionary(transition_fc),
#     sliceVisibilityThreshold: 0  // Don't group small slices.
#   });
# // print(transition_summary_chart);


# panel = ui.Panel({
#   style: {
#     width: '700px',
#     position: 'bottom-right',
#   },
#   layout: ui.Panel.Layout.flow('vertical'),
# });

# panel.add(transition_summary_chart);
# Map.add(panel);

