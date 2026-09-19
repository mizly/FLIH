from pathlib import Path
import json
from html import escape

original = json.loads(Path('.tmp-floor-plan/rooms.json').read_text())
parts = []
doors = []
labels = []
details = []

def n(v):
    return f'{v:g}'

def label(value, x, y, cls=''):
    attr = f' class="{cls}"' if cls else ''
    labels.append(f'    <text{attr} x="{n(x)}" y="{n(y)}">{escape(value)}</text>')

def door(x, y, side, width=25):
    # The gap and leaf share one origin on the actual wall.
    angle = {'left': 0, 'right': 180, 'top': -90, 'bottom': 90}[side]
    doors.append(f'    <g transform="translate({n(x)} {n(y)}) rotate({angle})"><path class="door-gap" d="M0 0v{width}"/><path class="door-leaf" d="M0 0h{width}"/></g>')

def room(name, x, y, w, h, side=None, pos=None, cls='room'):
    parts.append(f'    <rect id="room-{name}" class="{cls}" x="{n(x)}" y="{n(y)}" width="{n(w)}" height="{n(h)}"/>')
    label(name, x+w/2, y+h/2, 'small-label' if len(name)>4 or w<80 or h<48 else '')
    if side:
        offset = pos if pos is not None else (min(15,h-30) if side in ('left','right') else min(14,w-30))
        if side == 'left': door(x,y+offset,side)
        elif side == 'right': door(x+w,y+offset+25,side)
        elif side == 'top': door(x+offset,y,side)
        else: door(x+offset+25,y+h,side)

def shape(name, fill, wall, tx=None, ty=None):
    parts.append(f'    <g id="room-{name}"><path class="room-fill" d="{fill}"/><path class="wall" d="{wall}"/></g>')
    if tx is not None: label(name,tx,ty)

def stairs(name,x,y,w,h):
    room(name,x,y,w,h,None,cls='service')
    labels.pop()
    label(name,x+w/2,y+16,'small-label')
    details.append(f'    <path class="detail" d="M{x+12} {y+35}v{h-48}h{w-24}v-{h-48}M{x+w/2} {y+35}v{h-61}"/>')
    for yy in range(int(y+36),int(y+h-26),7):
        details.append(f'    <path class="detail" d="M{x+12} {yy}h{w-24}"/>')
    door(x+w,y+35,'right')

def shaft(name,x,y,w,h):
    parts.append(f'    <g id="{name}"><rect class="service" x="{x}" y="{y}" width="{w}" height="{h}"/><path class="detail" d="M{x} {y}l{w} {h}m-{w} 0l{w} -{h}"/></g>')

# E7 offices: retain the source-image coordinate system, correct the central
# blocks and give every office an entrance onto its adjoining hall.
skip = {'6912','6913','6914','6301','6022','6323','6333','6324','6338'}
for name,x,y,w,h in original:
    if x>=900 or name in skip or (name=='6328' and x==574): continue
    if name=='6446': x,w=464,64
    if name=='6448': x,y,w,h=574,46,109,98
    if name=='6427': x,w=206,162
    if name in ('6443','6447'): w=160
    if name=='6454': h=72
    if name in ('6309','6311'): x,w=206,162
    if name=='6313': y,h=1702,96
    if name in ('6321','6339'): h=96
    if x<=62:
        x,w=54,107
        side='right'
    elif x==574:
        w=109
        side='left'
    elif y<154 or y>=2150:
        side='bottom' if y<154 else 'top'
    elif name.startswith('6303'):
        side='right' if name[-1] in 'ABC' else 'left' if name[-1] in 'DEF' else 'top'
    else:
        side='left' if x<368 else 'right'
    room(name,x,y,w,h,side)

stairs('6854',574,297,109,197)
stairs('6856',206,920,62,138)
room('6911',206,847,62,73,'left',20,cls='service')
shaft('e7-north-shaft',206,810,62,37)
room('6912',278,810,88,185,'bottom',45,cls='service')
room('6913',366,847,88,148,'bottom',10,cls='service')
room('6916',454,847,74,95,'right',20,cls='service')
room('6914',454,942,74,53,'right',14,cls='service')
shaft('e7-core-shaft',366,810,162,37)
for name,x in [('6861',278),('6862',398),('6863',465)]:
    shaft('lift-'+name,x,995,58,63)
    label(name,x+29,1026,'small-label')
    door(x+18,1058,'bottom',22)
label('6301',108,1179)
label('6822',397,1179,'hall-label')
label('6364',632,1250,'small-label')
room('6323',206,1994,162,104,'left',22)
room('6333',368,1994,160,108,'right',22)
stairs('6827',54,2010,82,185)
stairs('6828',574,2010,109,172)
room('6919',104,1948,52,47,'bottom',12,cls='service')
shape('6324','M54 2195H202V2264H54Z','M54 2195H160M202 2195V2264',108,2233)
shape('6338','M528 2182H683V2264H528Z','M574 2182H683M528 2220V2264',613,2228)

# E5 north: the west stair and the two small rooms beside 6127 were absent.
room('6109',943,330,112,164,'bottom',45)
shape('6111','M1055 330H1255V494H1055Z','M1055 330V494H1110M1155 494H1255',1155,412)
shape('6112','M1255 330H1364V494H1255Z','M1255 494H1364M1364 330V494',1310,412)
room('6118',1364,330,95,94,'bottom',60)
room('6119',1459,330,103,154,'left',120)
room('6117',1348,557,65,38,'top',20)
room('6123',1348,595,65,95,'right',10)
room('6113',1098,557,85,91,'top',45)
room('6114',1183,557,73,133,'top',14)
room('6116',1256,557,92,133,'top',14)
room('6108',1098,648,85,91,'left',20)
shape('6106','M1098 739H1183V874H1098Z','M1098 739H1183V874H1098M1098 739V832',1140,800)
shape('6127','M1183 690H1413V874H1183Z','M1183 874V690H1413V825H1395',1295,775)
stairs('6807',943,557,81,197)
room('6904',1024,557,31,84,None,cls='service')
shaft('e5-north-stair-shaft',1024,641,31,113)
for name,y,h in [('6107',754,93),('6104',847,71),('6103',918,72),('6102',990,74)]:
    room(name,943,y,112,h,'right',12)
for name,y,h in [('6121',484,77),('6122',561,70),('6124',631,107),('6126',738,108),('6128',846,72),('6129',918,69),('6131',987,77)]:
    room(name,1459,y,103,h,'left',12)
shaft('e5-washroom-shaft',1098,874,112,44)
room('6903',1098,918,70,70,'left',32,cls='service')
room('6801',1098,988,58,76,'bottom',14,cls='service')
room('6802',1168,1000,65,64,'bottom',18,cls='service')
shape('6901','M1210 874H1275V1064H1233V990H1180V918H1210Z','M1210 874H1275V1064H1233V990H1180V918H1210Z',1235,942)
shape('6902','M1275 874H1355V1064H1233V1040H1275Z','M1275 874H1355V1064H1310M1275 874V1030H1300',1315,975)
shaft('e5-stair-shaft',1355,874,58,44)
stairs('6803',1355,918,58,146)
label('6808',1300,1093,'hall-label')
label('6101',997,1187)
label('6132',1510,1220)
room('6101A',956,1070,43,27,None,cls='service')
shaft('e5-atrium',1098,1203,315,115)
parts.append('    <rect id="e5-stairwell" class="service" x="1098" y="1142" width="315" height="61"/>')
label('5808',1255,1172,'small-label')
for xx in range(1140,1372,8):
    details.append(f'    <path class="detail" d="M{xx} 1152v41"/>')
parts.append('    <path class="wall" d="M1098 1123H1413M1098 1142H1413"/>')

# E5 south: 55 drawing units between x=1256 and x=1311 correspond
# to the 2.5 m dimension in the supplied image. Keep this spine continuous.
stairs('6804',943,1300,81,204)
shaft('e5-middle-stair-shaft',1024,1398,31,106)
label('6001',1040,1348,'small-label')
shape('6002','M1055 1398H1083V1360H1256V1504H1055Z','M1055 1398H1083M1083 1373V1360H1256V1504H1055V1398',1155,1432)
shape('6003','M1330 1382H1562V1504H1311V1428H1330Z','M1330 1397V1382H1562M1330 1428H1311V1504',1437,1450)
shape('6004','M1311 1504H1562V1664H1330V1610H1311Z','M1311 1504V1610H1330M1330 1658V1664H1562',1437,1580)
parts.append('    <path class="partition" d="M1311 1504H1562"/>')
shape('6005','M943 1522H1256V1688H1098V1735H943Z','M943 1522H1256V1637H1238V1522M943 1735H1098V1688H1256',1087,1620)
shaft('e5-middle-service',1098,1688,158,47)
shape('6007','M943 1735H1256V1948H943Z','M943 1735H1256M1236 1790H1256V1948H943',1087,1840)
shape('6006','M1311 1720H1562V1948H1330V1890H1311Z','M1330 1720H1311V1890H1330V1915M1330 1948H1562',1437,1800)
shape('6008','M1330 1948H1562V2238H1330V2183H1311V2000H1330Z','M1330 1948H1562M1330 1980V2000H1311V2183H1330M1330 2230V2238H1562',1437,2090)
stairs('6806',943,2010,81,185)
label('3006',1040,2090,'small-label')
shaft('e5-south-service',1098,2010,158,47)
shape('6014','M1098 2057H1175V2168H1098Z','M1098 2090V2168H1175V2057',1137,2118)
shape('6009','M1175 2057H1256V2168H1175Z','M1175 2057H1256V2074M1256 2110V2168H1175',1216,2118)
shape('6013','M943 2212H1098V2438H943Z','M943 2212H1065M1098 2212V2390M943 2438H1098',1018,2315)
shape('6012','M1098 2212H1256V2438H1098Z','M1098 2212H1208M1245 2212H1256V2438H1098',1177,2315)
shape('6011','M1311 2288H1330V2238H1562V2438H1311Z','M1330 2288H1311V2438H1562M1330 2238H1562',1437,2338)
details.append('    <path class="detail" d="M1350 1664l28 38h143l35 -38M1350 2238l28 -38h130l35 38"/>')

# The three links are enclosed corridors; the large spaces between them
# remain outside the floor plate. No vertical wall closes their endpoints.
header = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1590 2500" width="1590" height="2500" role="img" aria-labelledby="title desc">
  <title id="title">Engineering 5 and Engineering 7 sixth-floor plan</title>
  <desc id="desc">Vector floor plan traced against floor_plan.pdf, with connected hallways, three bridge passages, stair and elevator cores, and open common areas. The Engineering 5 corridor between rooms 6002 and 6003 is approximately 2.5 metres wide.</desc>
  <!-- Coordinates match the PDF image crop at (180, 120), 1590 by 2500 pixels.
       Scale reference: the E5 corridor from x=1256 to x=1311 is 55 px / 2.5 m.
       Pale green denotes circulation; dashed lines denote movable partitions. -->
  <style>
    .floor,.hallway{fill:#edf1eb}
    .room,.service{fill:#fff;stroke:#66706c;stroke-width:3}
    .service{fill:#f4f5f0}
    .room-fill{fill:#fff}
    .shell,.wall{fill:none;stroke:#66706c;stroke-width:3;stroke-linejoin:round}
    .shell{stroke-width:4}
    .detail{fill:none;stroke:#929a94;stroke-width:1.5}
    .partition{fill:none;stroke:#aab2aa;stroke-width:1.5;stroke-dasharray:9 6}
    .door-gap{fill:none;stroke:#edf1eb;stroke-width:7}
    .door-leaf{fill:none;stroke:#66706c;stroke-width:2}
    text{font-family:Arial,sans-serif;fill:#303633;text-anchor:middle;dominant-baseline:middle;font-size:19px}
    .small-label{font-size:14px}.hall-label{font-size:14px;fill:#72816f}
    .building{font-size:28px;font-weight:700;letter-spacing:2px}
  </style>
  <rect width="1590" height="2500" fill="#f8f8f2"/>
  <g id="corridors" aria-label="Connected hallways and bridge passages" data-reference-pixels="55" data-reference-meters="2.5">
    <rect id="e7-circulation" class="floor" x="54" y="46" width="629" height="2227"/>
    <rect id="e5-circulation" class="floor" x="943" y="330" width="619" height="2108"/>
    <path id="e7-west-hall" class="hallway" d="M161 153H206V1058H161Z"/>
    <path id="e7-east-hall" class="hallway" d="M528 153H574V2195H528Z"/>
    <path id="e7-central-lobby" class="hallway" d="M54 1064H683V1300H54Z"/>
    <path id="e7-south-hall" class="hallway" d="M161 1300H206V2150H528V2102H206V1300Z"/>
    <path id="e5-north-halls" class="hallway" d="M943 494H1459V557H1413V1064H1055V557H943Z"/>
    <path id="e5-south-spine" class="hallway" d="M1256 1318H1311V2438H1256Z"/>
    <path id="e5-south-loop" class="hallway" d="M943 1948H1330V2010H1055V2168H1256V2212H1024V2010H943Z"/>
    <rect id="bridge-6852" class="hallway" x="683" y="494" width="260" height="63"/>
    <rect id="bridge-6834" class="hallway" x="683" y="1064" width="260" height="136"/>
    <rect id="bridge-6831" class="hallway" x="683" y="1948" width="260" height="62"/>
  </g>
  <g id="building-walls">
    <path class="shell" d="M683 494V46H54V2273H683V2010M683 1948V1200M683 1064V557"/>
    <path class="shell" d="M943 494V330H1562V2438H943V2010M943 1948V1200M943 1064V557"/>
    <path class="shell" d="M683 494H943M683 557H943M683 1064H943M683 1200H943M683 1948H943M683 2010H943"/>
  </g>
'''
for value,x,y in [('6851',375,180),('6853',365,524),('6847',182,350),('6849',551,710),('6823',181,1825),('6829',550,1750),('6826',381,2128),('6832',620,1979),('6855',624,524),('6852',813,524),('6834',813,1132),('6831',813,1979),('6809',1021,524),('6811',1260,524),('6809',1076,806),('6811',1437,750),('6812',1437,982),('6809',1190,1336),('6812',1283,1395),('6812',1283,1892),('6813',1177,1977),('6813',1178,2190),('6812',1283,2240)]:
    label(value,x,y,'hall-label')
label('ENGINEERING 7',365,2325,'building')
label('ENGINEERING 5',1245,2470,'building')
svg = header + '  <g id="rooms">\n'+'\n'.join(parts)+'\n  </g>\n  <g id="core-details" aria-hidden="true">\n'+'\n'.join(details)+'\n  </g>\n  <g id="doors" aria-label="Room entrances">\n'+'\n'.join(doors)+'\n  </g>\n  <g id="labels">\n'+'\n'.join(labels)+'\n  </g>\n</svg>\n'
Path('frontend/public/floor-plan.svg').write_text(svg,encoding='utf-8')
