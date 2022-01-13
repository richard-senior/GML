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

Intended future functionality includes:
* Full lexical parsing (python PLY lex/yacc) of GCode (plus bespoke extensions) syntax
* Import directly from SVG (no need for GCodeTools export) and export to SVG (for quick visualisation)
* Contributing (or doing something similar) to GCodeTools (adding another set of post processing methods?)
* more manipulation functions including : 
  * auto path fill using cross hatch or path dilation (the eggbot tools are unreliable)
  * Auto tool diameter change refactoring
  * ..
  

## Current Funtionality
* Parses output (.nc) from the [Inkscape GCodeTools extension](https://github.com/cnc-club/gcodetools)
  Breaks the code into 'blocks' based upon various hueristics (z axis up/down, G00 codes, M5 etc.)
  Allows manipulation of code or blocks of code (extrude, translate, rotate, reverse more to come)
  Auto adds standard headers (start spindle etc.) and footers (return to x0,y0,z0 ready for next pass)
* Parses output from the [Python svg-to-gcode library](https://pypi.org/project/svg-to-gcode/)
  Blockifies it (as with GCodeTools) and provides the same manipulation functionality.
  
## Usage

Begin by drawing the paths to engrave in Inkscape and using the GCodeTools plugin to export
the paths to a .nc file.
You can find many videos on YouTube to demonstrate this by searching simply for "Inkscape GCodeTools".

Create a python file and write code such as:
```python
# import the main class of this tool set
import GrblCommand.GrblCommand

# set some constants which are static member variables of the class
# these constants will allow you to achieve certain routine tasks
GrblCommand.fast_travel_speed = 800
GrblCommand.evacuation_height = 1
GrblCommand.cut_speed = 80
GrblCommand.autoBlockSort = True

# process the nc file exported from Inkscape
foo = GrblCommand.processGrbl("/temp/raw.nc","/temp/processed.nc")
# You may use the response (foo) to continue working on the GCode if desired, or just ignore it.
# for example
foo = foo.rotateBlock(90, 100, 100, 3)
foo.burp("/temp/rotated_block.nc")
```

## Example

Begin by creating a path in Inkscape etc. (an SVG) ie:

![alt text](https://github.com/richard-senior/GML/blob/main/a.svg?raw=true)

You can actually directly import this using (GrblCommand.processSvg(in,out)) but I'll properly document that later
when the functionality is imporoved

use GCodeTools to export this to GCode which gives something like:

```
(Header)
(Generated by gcodetools from Inkscape.)
(Using default header. To add your own header create file "header" in the output dir.)
M3
(Header end.)
G21 (All units in mm)

(Pass at depth -1.0)
(Start cutting path id: path12970-7)
(Change tool to Default tool)

G00 Z1.000000
G00 X7.190691 Y-0.249861

G01 Z-0.350000 F100.0(Penetrate)
G03 X6.770763 Y-0.227642 Z-0.350000 I-0.385601 J-3.308426 F400.000000
G03 X6.343031 Y-0.253861 Z-0.350000 I0.043390 J-4.210064
G02 X6.335398 Y-0.254754 Z-0.350000 I-0.018487 J0.124915
G03 X6.327431 Y-0.255861 Z-0.350000 I0.006657 J-0.077151
G01 X1.596960 Y-0.638680 Z-0.350000
G02 X1.576460 Y-0.639099 Z-0.350000 I-0.020500 J0.501518
G02 X1.555960 Y-0.638680 Z-0.350000 I0.000000 J0.501937
G03 X1.492103 Y-0.642595 Z-0.350000 I0.011940 J-0.717624
G03 X1.421200 Y-0.652380 Z-0.350000 I0.120604 J-1.135605
G03 X1.355056 Y-0.670916 Z-0.350000 I0.052001 J-0.312844
G01 X1.347000 Y-0.658380 Z-0.350000
G01 X1.355355 Y-0.664746 Z-0.350000
G03 X1.335300 Y-0.711080 Z-0.350000 I0.263253 J-0.141448
G03 X1.309025 Y-0.801834 Z-0.350000 I1.172007 J-0.388499
G03 X1.308000 Y-0.806780 Z-0.350000 I0.062543 J-0.015541
G01 X1.308000 Y-0.810780 Z-0.350000
G01 X1.140040 Y-2.404460 Z-0.350000
G01 X5.515040 Y-2.041181 Z-0.350000
G02 X5.518040 Y-2.041173 Z-0.350000 I0.003000 J-0.600000
G02 X5.521040 Y-2.041181 Z-0.350000 I-0.000000 J-0.600008
G02 X5.877502 Y-2.073000 Z-0.350000 I0.079807 J-1.118529
G02 X6.255400 Y-2.302901 Z-0.350000 I-0.186287 J-0.731742
G02 X6.440683 Y-2.696005 Z-0.350000 I-0.574396 J-0.510949
G02 X6.444870 Y-3.047041 Z-0.350000 I-1.225883 J-0.190164
G01 X5.797680 Y-8.358671 Z-0.350000
G03 X5.796880 Y-8.363624 Z-0.350000 I0.166861 J-0.029479
G01 X5.795680 Y-8.368671 Z-0.350000
G02 X5.720324 Y-8.685594 Z-0.350000 I-1.563235 J0.204274
G02 X5.532020 Y-9.009291 Z-0.350000 I-0.935986 J0.327871
G02 X5.220319 Y-9.240063 Z-0.350000 I-0.680098 J0.592709
G02 X4.848430 Y-9.333511 Z-0.350000 I-0.451011 J1.008147
G01 X3.275589 Y-9.480691 Z-0.350000
G02 X2.938791 Y-9.459774 Z-0.350000 I-0.095126 J1.190245
G02 X2.547069 Y-9.234591 Z-0.350000 I0.146279 J0.707770
G02 X2.365178 Y-8.831545 Z-0.350000 I0.544289 J0.488199
G02 X2.367399 Y-8.500221 Z-0.350000 I1.336404 J0.156709
G02 X2.465760 Y-7.792304 Z-0.350000 I132.012073 J-17.981436
G02 X2.684590 Y-6.286571 Z-0.350000 I210.482885 J-29.820925
G02 X3.245979 Y-5.679203 Z-0.350000 I0.698679 J-0.082658
G02 X4.035510 Y-5.557701 Z-0.350000 I1.783927 J-8.966154
G02 X4.130575 Y-4.853641 Z-0.350000 I15.053679 J-1.674166
G03 X4.227480 Y-4.132661 Z-0.350000 I-14.930985 J2.373834
G03 X2.956102 Y-4.243622 Z-0.350000 I9.203154 J-112.787493
G02 X1.842960 Y-4.343621 Z-0.350000 I-16.681498 J179.446053
G03 X1.375505 Y-4.469924 Z-0.350000 I0.119880 J-1.371865
G03 X1.130070 Y-4.652221 Z-0.350000 I0.331079 J-0.702121
G03 X0.928775 Y-4.979793 Z-0.350000 I0.785261 J-0.708182
G03 X0.761970 Y-5.652951 Z-0.350000 I2.588702 J-0.998713
G01 X0.343439 Y-9.488641 Z-0.350000
G01 X0.343439 Y-9.490641 Z-0.350000
G03 X0.325235 Y-10.182703 Z-0.350000 I3.769670 J-0.445430
G03 X0.464539 Y-10.670331 Z-0.350000 I1.195613 J0.077847
G03 X0.733014 Y-10.940988 Z-0.350000 I0.588018 J0.314793
G03 X1.622739 Y-11.170331 Z-0.350000 I0.898986 J1.647076
G01 X6.532890 Y-10.740612 Z-0.350000
G02 X6.536862 Y-10.739720 Z-0.350000 I0.085851 J-0.373267
G01 X6.540890 Y-10.738612 Z-0.350000
G03 X7.037208 Y-10.621809 Z-0.350000 I-0.114167 J1.598000
G03 X7.290890 Y-10.453452 Z-0.350000 I-0.299420 J0.726471
G03 X7.466323 Y-10.198059 Z-0.350000 I-0.583316 J0.588639
G03 X7.613160 Y-9.658532 Z-0.350000 I-1.734510 J0.761807
G01 X8.454951 Y-1.967131 Z-0.350000
G01 X8.454951 Y-1.963131 Z-0.350000
G03 X8.261333 Y-0.847061 Z-0.350000 I-2.134526 J0.204529
G03 X7.908081 Y-0.461181 Z-0.350000 I-0.795496 J-0.373602
G03 X7.600865 Y-0.331084 Z-0.350000 I-0.664206 J-1.140692
G03 X7.191281 Y-0.250241 Z-0.350000 I-0.715460 J-2.546845
G01 X7.190691 Y-0.249861 Z-0.350000
G00 Z1.000000

(End cutting path id: path12970-7)


(Pass at depth -2.0)

(Footer)
M5
G00 X0.0000 Y0.0000
M2
(Using default footer. To add your own footer create file "footer" in the output dir.)
(end)
```

Use a tool like [nc viewer](https://ncviewer.com/) to check the GCode (looks like this):

![alt text](https://github.com/richard-senior/GML/blob/main/ghpic.png?raw=true)

## contributing
I realise this code is a mess. I literally hacked it together to perform a task I needed doing at the time.
I want to begin refactoring this to use PLY for the parsing of the GCODE import, perhaps use Lexx to break
the code into blocks based on various hueristics, rather than by postprocessing LexToken's manually.
If you wish to help or offer feature suggestions, please let me know.
