import sys, enum
import xml.etree.ElementTree as ET

EXTRUDE_RATE = -.1 # Extrusion amount per mm
FEED_RATE = 378 # Movement rate
PRINT_AREA = (100, 100) # size in mm of printable area
scaling = (1, 1)
offset = (50, 50)

class COMMAND(enum.Enum):
	move = 0
	line = 1
	curve = 2

class POSITION(enum.Enum):
	absolute = 0
	relative = 1

def extract_namespace(tag):
	if tag.startswith("{") and "}" in tag:
		return tag[:tag.index("}")+1]
	else:
		return ""

def pt_avg(p1, p2, t):
	return ((1-t) * p1[0] + t * p2[0], (1-t) * p1[1] + t * p2[1])

def euc_dist(p1, p2):
	return ((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2) ** .5

def interpolate_step(pts, step):
	for i in xrange(len(pts)-1, 0, -1):
		newpts = [0] * i
		for pt_idx in xrange(i):
			newpts[pt_idx] = pt_avg(pts[pt_idx], pts[pt_idx+1], step)
		pts = newpts
	return newpts[0]

def interpolate(pts, num_steps):
	step_size = 1./(num_steps-1)
	results = []
	for i in xrange(num_steps):
		results.append(interpolate_step(pts, step_size * i))
	return results

def convert_to_gcode(svg):
	print("""G21        ;metric values
G90        ;absolute positioning
M82        ;set extruder to absolute mode
M107       ;start with the fan off
G28 X0 Y0  ;move X/Y to min endstops
G28 Z0     ;move Z to min endstops
M302
M92 E12000
G1 Z15.0 F9000 ;move the platform down 15mm
G92 E0                  ;zero the extruded length
G1 F200 E3              ;extrude 3mm of feed stock
G92 E0                  ;zero the extruded length again
G1 F9000

;Layer count: 1
;LAYER:0
M107
G1 F1200
G0 Z0.3000
;TYPE:WALL-OUTER""")
	root = ET.fromstring(svg)
	ns = extract_namespace(root.tag)
	g = root.findall(ns+"g")[0]
	paths = g.findall(ns+"path")
	width = root.get("width")
	height = root.get("height")
	transform = g.get("transform")
	if width and height:
		w = float(width.rstrip("pt"))
		h = float(height.rstrip("pt"))
		if transform:
			scale_string = transform[transform.index("scale(") + len("scale("):-1]
			sx, sy = map(float, scale_string.split(","))
			w /= sx
			h /= -sy
		scaling = (PRINT_AREA[0] / w, PRINT_AREA[1] / h)
	instructions = []
	for path in paths:
		directions = path.get("d")
		for direction in directions.split(" "):
			direction = direction.rstrip("z")
			if str.isalpha(direction[0]):
				instructions.append(direction[0])
				if len(direction) > 1:
					instructions.append(direction[1:])
			else:
				instructions.append(direction)
	command_type = instructions[0]
	position = POSITION.absolute
	assert str.isalpha(command_type)
	current_point = (0, 0)
	extrude_amt = 0
	while len(instructions) > 0:
		directive = instructions.pop(0)
		if directive.lower() == "m":
			command_type = COMMAND.move
			if str.isupper(directive):
				position = POSITION.absolute
			else:
				position = POSITION.relative
		elif directive.lower() == "l":
			command_type = COMMAND.line
			if str.isupper(directive):
				position = POSITION.absolute
			else:
				position = POSITION.relative
		elif directive.lower() == "c":
			command_type = COMMAND.curve
			if str.isupper(directive):
				position = POSITION.absolute
			else:
				position = POSITION.relative
		elif str.isalpha(directive):
			print "[ERROR] Unrecognized directive:", directive
			sys.exit(0)
		else:
			secondary = instructions.pop(0)
			px = int(directive) * scaling[0] + offset[0]
			py = int(secondary) * scaling[1] + offset[1]
			if position == POSITION.relative:
				px = int(directive) * scaling[0] + current_point[0]
				py = int(secondary) * scaling[1] + current_point[1]
			if command_type == COMMAND.move:
				#print "=== MOVE", px, py
				print "G01", "Z1.2000"
				print "G01", "X" + `px`, "Y" + `py`, "F9000"
				print "G01", "Z0.3000"
				current_point = (px, py)
			elif command_type == COMMAND.line:
				dist = euc_dist(current_point, (px, py))
				extrude_amt += dist * EXTRUDE_RATE
				#print "=== LINE", px, py, extrude_amt
				print "G01", "X" + `px`, "Y" + `py`, "E" + `extrude_amt`, "F" + `FEED_RATE`
				current_point = (px, py)
			elif command_type == COMMAND.curve:
				f1 = instructions.pop(0)
				f2 = instructions.pop(0)
				f3 = instructions.pop(0)
				f4 = instructions.pop(0)
				pt2 = (int(f1) * scaling[0] + offset[0], int(f2) * scaling[1] + offset[1])
				pt3 = (int(f3) * scaling[0] + offset[0], int(f4) * scaling[1] + offset[1])
				if position == POSITION.relative:
					pt2 = (int(f1) * scaling[0] + current_point[0], int(f2) * scaling[1] + current_point[1])
					pt3 = (int(f3) * scaling[0] + current_point[0], int(f4) * scaling[1] + current_point[1])
				points = [current_point, (px, py), pt2, pt3]
				num_step = 10 #make func of dist?
				interpolated = interpolate(points, num_step)
				#print "=== CURVE", points
				for pt in interpolated:
					dist = euc_dist(current_point, pt)
					current_point = pt
					extrude_amt += dist * EXTRUDE_RATE
					print "G01", "X" + `pt[0]`, "Y" + `pt[1]`, "E" + `extrude_amt`, "F" + `FEED_RATE`
	print """M104 S0                     ;extruder heater off
M140 S0                     ;heated bed heater off (if you have it)
G91                                    ;relative positioning
G1 E-1 F300                            ;retract the filament a bit before lifting the nozzle, to release some of the pressure
G1 Z+0.5 E-5 X-20 Y-20 F9000 ;move Z up a bit and retract filament even more
G28 X0 Y0                              ;move X/Y to min endstops, so the head is out of the way
M84                         ;steppers off
G90                         ;absolute positioning"""

if __name__ == "__main__":
	convert_to_gcode(sys.stdin.read())
	# pts = [(90, 110), (25, 40), (230, 40), (150, 240)]
	# print interpolate(pts, 10)
