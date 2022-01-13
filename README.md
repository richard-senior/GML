# GML

GCode Markup Language

The intention is to eventually create something a little like [Linux CNC](http://linuxcnc.org/) for use
with inexpensive low end (hobbyist) CNC engraving, drawing, and laser cutting machines.

Currently the main functionality provided can already be achieved using Inkscape and the GCodeTools extension
(see below). But having to return to Inkscape, modify and re-export constantly just to make small modifications
can be cumbersome. This project allows modifications to GCode directly without having to use Inkscape etc.

So for example you may find that the GCode exported from GCodeTools is correct but that you wish to 
temporarily move the whole engraving 1mm to the right, or to rotate it all by 10 degrees (to fit the
blank material you currently have etc.)

Or you may wish for the machine to return to zero after every path cut (so you can trial something) etc.

## Current Funtionality
* Parses output (.nc) from the [Inkscape GCodeTools extension](https://github.com/cnc-club/gcodetools)
  Breaks the code into 'blocks' based upon various hueristics (z axis up/down, G00 codes, M5 etc.)
  Allows manipulation of code or blocks of code (extrude, translate, rotate.. more to come)
  Auto adds standard headers (start spindle etc.) and footers (return to x0,y0,z0 ready for next pass)
  Eventually will provide various export formats such as SVG etc.
* Parses output from the [Python svg-to-gcode library](https://pypi.org/project/svg-to-gcode/)
  Blockifies it (as with GCodeTools) and provides the same manipulation functionality.
  
## Example Usage

Begin by drawing the paths to engrave in Inkscape and using the GCodeTools plugin to export
the paths to a .nc file.
You can find many videos on YouTube to demonstrate this by searching simply for "Inkscape GCodeTools".

Create a python file and write code such as:
```python
# import the main class of this tool set
import GrblCommand.GrblCommand

# set some constants which are static member variables of the class
GrblCommand.fast_travel_speed = 800
GrblCommand.evacuation_height = 1
GrblCommand.cut_speed = 80
GrblCommand.autoBlockSort = True

# process the nc file exported from Inkscape
foo = GrblCommand.processGrbl("/temp/raw.nc","/temp/processed.nc")
# You may use the response (foo) to continue working on the GCode if desired, or just ignore it.
```
