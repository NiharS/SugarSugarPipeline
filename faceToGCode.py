import cv2
import os
import sys

if len(sys.argv) != 2:
    print "USAGE: python outline.py <image>"
    sys.exit(0)
fname = sys.argv[1]
bname = fname[:fname.rfind(".")]
oname = bname + "_outline.png"
if not "." in oname:
    oname = fname + "_outline.png"
img = cv2.imread(fname, -1)
edges = cv2.Canny(img, 80, 110)
edges = 255-edges
cv2.imwrite(oname, edges)
os.system("pngtopnm -mix %s > %s.pnm && potrace %s.pnm -k .5 -s -o %s.svg" % (oname, bname, bname, bname))
os.system("cat %s.svg | python svgToGCode.py > %s.gcode" % (bname, bname))