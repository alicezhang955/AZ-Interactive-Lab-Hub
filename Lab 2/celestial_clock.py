import time
from time import strftime, sleep
import subprocess
import digitalio
import board
from PIL import Image, ImageDraw, ImageFont
import adafruit_rgb_display.st7789 as st7789
import ephem
import math
import re
from urllib import request
import numpy as np
from datetime import datetime
import geoip2.database
import signal


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


def alt_to_y(alt):
    y_coord = origin[1] - alt / 90 * y_rad
    return y_coord

def az_to_x(az):
    x_coord = origin[0] - x_rad * math.sin(math.pi*az/180)
    return x_coord


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

def draw_clock():
    for i in range(12):
        rads = math.radians(i * 30)
        x1 = origin[0] + (.7*x_rad - 1) * math.cos(rads) 
        x2 = origin[0] + (.7*x_rad + 1) * math.cos(rads)
        y1 = origin[1] + (.5*y_rad - 1) * math.sin(rads)
        y2 = origin[1] + (.5*y_rad + 1) * math.sin(rads)
        draw.line(xy = [x1, y1, x2, y2],
                fill = (255, 255, 255),
                width = 1)

def draw_horizon():
    draw.line(xy = [0, origin[1], width, origin[1]],
            fill = (255, 255, 255),
            width = 1)

def set_background():
    draw.rectangle((0, 0, width, height), outline=0, fill=0)
    draw_clock()
    draw_horizon()

def get_ip(url='http://checkip.dyndns.org'):
    response = request.urlopen(url).read().decode('utf-8')
    return re.findall(r"\d{1,3}\.\d{1,3}\.\d{1,3}.\d{1,3}", response)[0]

def get_location(ip, fname='./data/GeoLiteCity.dat'):
    """Database can be downloaded at:
        http://dev.maxmind.com/geoip/legacy/geolite/"""
    reader = geoip2.database.Reader("GeoLite2-City.mmdb")
    response = reader.city(ip)
    return response

def compute_phase(moon, obs):
    nnm = ephem.next_new_moon(obs.date)  
    pnm = ephem.previous_new_moon(obs.date)  
    lunation = (obs.date - pnm) / (nnm - pnm) 
    moon.compute(obs)

    # MOON PHASES
    # {0, new moon
    # 1, waxing crescent
    # 2, first quarter
    # 3, waxing gibbous
    # 4, full moon
    # 5, waning gibbous
    # 6, last quarter
    # 7, waning crescent}

    if lunation < .015 or lunation >= .985: #New Moon
        moon_phase = 0
        e_rad = 0
    elif lunation < .235: #Waxing Crescent
        moon_phase = 1
        e_rad = (1 - moon.phase / 100) * e_max_rad
    elif lunation < .265: #First Quarter
        moon_phase = 2
        e_rad = 0
    elif lunation < .485: #Waxing Gibous
        moon_phase = 3
        e_rad = (moon.phase - 50) / 100 * e_max_rad
    elif lunation < .515: #Full Moon
        moon_phase = 4
        e_rad = 0
    elif lunation < .735: #Waning Gibbous
        moon_phase = 5
        e_rad = (moon.phase - 50) / 100 * e_max_rad
    elif lunation < .765: #Last Quarter
        moon_phase = 6
        e_rad = 0
    else: #Waning Crescent
        moon_phase = 7
        e_rad = (1 - moon.phase / 100) * e_max_rad

    return e_rad, moon_phase

def draw_moon(coord, e_rad, moon_phase):
    match moon_phase:
        case 0: new_moon(coord)
        case 1: waxing_crescent(coord, e_rad)
        case 2: first_quarter(coord)
        case 3: waxing_gibbous(coord, e_rad)
        case 4: full_moon(coord)
        case 5: waning_gibbous(coord, e_rad)
        case 6: last_quarter(coord)
        case 7: waning_crescent(coord, e_rad)

# -----------------------------
# Cleanup on exit
# -----------------------------
def cleanup(signalnum=None, frame=None):
    print("\nCleaning up GPIO pins...")
    cs_pin.deinit()
    dc_pin.deinit()
    backlight.deinit()
    exit(0)

signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)



#VISUAL CONFIGURABLES
origin = [width / 2, height / 2]
y_rad = 80
x_rad = 100
rad = 10
e_max_rad = 9


#World setup
ip = get_ip()
location = get_location(ip)
date = datetime.utcnow()
moon = ephem.Moon()
obs = ephem.Observer()
obs.date = date 
obs.lon = str(location.location.longitude)
obs.lat = str(location.location.latitude)
e_rad, moon_phase = compute_phase(moon, obs)

#Loop over one day
az, alt, = [], []

for k in range(24):
    moon.compute(obs)  
    alt.append(moon.alt)
    az.append(moon.az)
    obs.date += ephem.hour

az, alt = map(np.rad2deg, (az, alt))

#Walk through next 24 hours
for x, y in zip(az, alt):
    #Set coords
    y_coord = alt_to_y(y)
    x_coord = az_to_x(x)
    coord = [x_coord, y_coord]

    #Draw moon
    set_background()
    draw_moon(coord, e_rad, moon_phase)
    disp.image(image, rotation)

    time.sleep(1)

while True:
    #World setup
    date = datetime.utcnow()
    moon = ephem.Moon()
    obs = ephem.Observer()
    obs.date = date 
    obs.lon = str(location.location.longitude)
    obs.lat = str(location.location.latitude)
    moon.compute(obs) 

    #Compute coords, moon phase
    y_coord = alt_to_y(np.rad2deg(moon.alt))
    x_coord = az_to_x(np.rad2deg(moon.az))
    coord = [x_coord, y_coord]
    e_rad, moon_phase = compute_phase(moon, obs)

    #Draw moon
    set_background()
    draw_moon(coord, e_rad, moon_phase)
    disp.image(image, rotation)

    time.sleep(1)
