import time
from time import strftime, sleep
import subprocess
import digitalio
import board
from PIL import Image, ImageDraw, ImageFont
import adafruit_rgb_display.st7789 as st7789
import ephem


# Configuration for CS and DC pins (these are FeatherWing defaults on M0/M4):
cs_pin = digitalio.DigitalInOut(board.D5) 
dc_pin = digitalio.DigitalInOut(board.D25)
reset_pin = None

# Config for display baudrate (default max is 24mhz):
BAUDRATE = 64000000

# Setup SPI bus using hardware SPI:
spi = board.SPI()

# Create the ST7789 display:
disp = st7789.ST7789(
    spi,
    cs=cs_pin,
    dc=dc_pin,
    rst=reset_pin,
    baudrate=BAUDRATE,
    width=135,
    height=240,
    x_offset=53,
    y_offset=40,
)

# Create blank image for drawing.
# Make sure to create image with mode 'RGB' for full color.
height = disp.width  # we swap height/width to rotate it to landscape!
width = disp.height
image = Image.new("RGB", (width, height))
rotation = 90

# Get drawing object to draw on image.
draw = ImageDraw.Draw(image)

# Draw a black filled box to clear the image.
draw.rectangle((0, 0, width, height), outline=0, fill=(255, 0, 255))
disp.image(image, rotation)
# Draw some shapes.
# First define some constants to allow easy resizing of shapes.
padding = -2
top = padding
bottom = height - padding
# Move left to right keeping track of the current x position for drawing shapes.
x = 0

# Alternatively load a TTF font.  Make sure the .ttf font file is in the
# same directory as the python script!
# Some other nice fonts to try: http://www.dafont.com/bitmap.php
font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)

# Turn on the backlight
backlight = digitalio.DigitalInOut(board.D22)
backlight.switch_to_output()
backlight.value = True

coord = [0, 0]
rad = 20

def full_moon(coord):
    draw.circle(xy = coord, 
            radius = rad,
            fill = (255, 255, 255),
            outline = None,
            width = 5)

def first_quarter(coord):
    draw.chord(xy = [coord[0] - rad, coord[1] - rad, coord[0] + rad, coord[1] + rad],
            start = 270,
            end = 90,
            fill = (255, 255, 255),
            width = 5)

def last_quarter(coord):
    draw.chord(xy = [coord[0] - rad, coord[1] - rad, coord[0] + rad, coord[1] + rad],
            start = 90,
            end = 270,
            fill = (255, 255, 255),
            width = 5)

def waxing_crescent(coord, e_rad):
    first_quarter(coord)
    draw.ellipse(xy = [coord[0] - e_rad, coord[1] - rad, coord[0] + e_rad, coord[1] + rad],
            outline = None,
            fill = (0, 0, 0),
            width = 5)

def waning_crescent(coord, e_rad):
    last_quarter(coord)
    draw.ellipse(xy = [coord[0] - e_rad, coord[1] - rad, coord[0] + e_rad, coord[1] + rad],
            outline = None,
            fill = (0, 0, 0),
            width = 5)

def waning_gibbous(coord, e_rad):
    last_quarter(coord)
    draw.ellipse(xy = [coord[0] - e_rad, coord[1] - rad, coord[0] + e_rad, coord[1] + rad],
            outline = None,
            fill = (255, 255, 255),
            width = 5)

def waxing_gibbous(coord, e_rad):
    first_quarter(coord)
    draw.ellipse(xy = [coord[0] - e_rad, coord[1] - rad, coord[0] + e_rad, coord[1] + rad],
            outline = None,
            fill = (255, 255, 255),
            width = 5)

def new_moon(coord):
    draw.circle(xy = coord, 
            radius = rad,
            fill = (255, 255, 255),
            outline = None,
            width = 1)
    draw.circle(xy = coord, 
            radius = rad-1,
            fill = (0, 0, 0),
            outline = None,
            width = 1)

while True:
    moon = ephem.Moon()
    moon.compute('1986/2/8') #figure out date
    moon_location = ephem.Equatorial(moon, epoch=ephem.B1950) #figure out epoch
    
    
    print(m.moon_phase)

    # Draw a black filled box to clear the image.
    coord = [width / 2, height / 2]
    draw.rectangle((0, 0, width, height), outline=0, fill=0)
    new_moon(coord)


    #TODO: Lab 2 part D work should be filled in here. You should be able to look in cli_clock.py and stats.py 

    #get clock time
    current_time = strftime("%m/%d/%Y %H:%M:%S")
    
    #Write line of text
    y = top
    draw.text((x, y), current_time, font=font, fill="#FFFFFF")
    bbox = font.getbbox(current_time)
    y += bbox[3] - bbox[1]

    # coord[0] += 10
    # coord[1] += 10

    if(coord[0] > width or coord[1] > height):
        coord = [0,0]

    # Display image.
    disp.image(image, rotation)
    time.sleep(1)
