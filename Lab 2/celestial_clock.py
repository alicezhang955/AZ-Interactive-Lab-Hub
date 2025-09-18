import time
from time import strftime, sleep
import subprocess
import digitalio
import board
from PIL import Image, ImageDraw, ImageFont
import adafruit_rgb_display.st7789 as st7789
import ephem

from astropy.time import Time
from astropy.coordinates import EarthLocation, AltAz
import astropy.units as u
import math
import re
from urllib import request
from pygeoip import GeoIP
import numpy as np
from datetime import datetime
import geoip2.database


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

def alt_az(ra_hours, dec_deg, lat_deg, lst_hours):
    """
    Compute Altitude and Azimuth of a celestial object.

    Parameters:
        ra_hours: Right Ascension in hours
        dec_deg: Declination in degrees
        lat_deg: Observer latitude in degrees
        lst_hours: Local Sidereal Time in hours

    Returns:
        altitude_deg, azimuth_deg
    """

    # Convert everything to radians
    ra_rad = math.radians(ra_hours * 15)       # 15° per hour
    dec_rad = math.radians(dec_deg)
    lat_rad = math.radians(lat_deg)
    lst_rad = math.radians(lst_hours * 15)     # 15° per hour

    # Hour Angle HA = LST - RA
    ha_rad = lst_rad - ra_rad

    # Altitude formula
    sin_alt = math.sin(dec_rad) * math.sin(lat_rad) + \
              math.cos(dec_rad) * math.cos(lat_rad) * math.cos(ha_rad)
    alt_rad = math.asin(sin_alt)

    # Azimuth formula
    cos_az = (math.sin(dec_rad) - math.sin(alt_rad) * math.sin(lat_rad)) / \
             (math.cos(alt_rad) * math.cos(lat_rad))
    # To handle rounding errors that may push cos_az slightly >1 or < -1
    cos_az = min(1.0, max(-1.0, cos_az))
    az_rad = math.acos(cos_az)

    # Determine correct quadrant for azimuth
    if math.sin(ha_rad) > 0:
        az_rad = 2 * math.pi - az_rad

    # Convert to degrees
    altitude_deg = math.degrees(alt_rad)
    azimuth_deg = math.degrees(az_rad)

    return altitude_deg, azimuth_deg

def time_to_hours(time_str):
    """
    Convert a string of format 'XhYmZs' to hours as a float.
    Example: '2h30m45s' -> 2.5125 hours
    """
    hours = minutes = seconds = 0

    # Find hours, minutes, seconds using regex
    h_match = re.search(r'(\d+)h', time_str)
    m_match = re.search(r'(\d+)m', time_str)
    s_match = re.search(r'(\d+)s', time_str)

    if h_match:
        hours = int(h_match.group(1))
    if m_match:
        minutes = int(m_match.group(1))
    if s_match:
        seconds = int(str(time_str[6] + time_str[7])) #Manually count indices of seconds chars

    total_hours = hours + minutes/60 + seconds/3600 
    return total_hours

def alt_to_y(alt):
    y_coord = origin[1] + alt / 90 * y_rad
    print("ycoord", y_coord)
    return y_coord

def az_to_x(az):
    x_coord = 0
    # if 0 < az < 90:
    #     x_coord = origin[0] + x_rad * (az) / 90
    # elif 270 < az < 360:
    #     x_coord = origin[0] - x_rad * (360 - az) / 90
    # elif 180 < az < 270:
    #     x_coord = origin[0] - x_rad * (az - 180) / 90
    # elif 90 < az < 180:
    #     x_coord = origin[0] + x_rad * (180 - az) / 90

    if 0 < az < 90:
        x_coord = origin[0] + x_rad * math.sin(math.pi*az/180)
        print("xcoord", x_coord)
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

def moon_halo(coord):
    draw.circle(xy = coord, 
            radius = rad + 4,
            fill = (0, 0, 0),
            outline = None,
            width = 1)

def draw_clock():
    for i in range(12):
        rads = math.radians(i * 30)
        x1 = origin[0] + (x_rad - 1) * math.cos(rads) 
        x2 = origin[0] + (x_rad + 1) * math.cos(rads)
        y1 = origin[1] + (y_rad - 1) * math.sin(rads)
        y2 = origin[1] + (y_rad + 1) * math.sin(rads)
        draw.line(xy = [x1, y1, x2, y2],
                fill = (255, 255, 255),
                width = 1)
        # print(x1, y1)

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



#VISUAL CONFIGURABLES
origin = [width / 2, height / 2]
y_rad = 80
x_rad = 100
rad = 10
e_rad = 2

#World setup
ip = get_ip()
location = get_location(ip)
date = datetime.utcnow()
moon = ephem.Moon()
obs = ephem.Observer()
obs.date = date
obs.lon = np.deg2rad(location.location.longitude)
obs.lat = np.deg2rad(location.location.latitude)


#Loop over one day
az, alt, symbols, times = [], [], [], []

for k in range(24):
    moon.compute(obs)  
  
    nnm = ephem.next_new_moon(obs.date)  
    pnm = ephem.previous_new_moon(obs.date)  
    lunation = (obs.date - pnm) / (nnm - pnm)  
    symbol = lunation * 26
    if symbol < 0.2 or symbol > 25.8:
        symbol = '1'
    else:  
        symbol = chr(ord('A') + int(symbol + 0.5) - 1)
        times.append(ephem.localtime(obs.date).time().strftime("%H:%M"))
        symbols.append(symbol)
        alt.append(moon.alt)
        az.append(moon.az)
    
    obs.date += ephem.hour
    
az, alt = map(np.rad2deg, (az, alt))

#Walk through next 24 hours
for x, y, text in zip(az, alt, symbols):
    #Set coords
    y_coord = alt_to_y(y)
    x_coord = az_to_x(x)
    print(x)
    coord = [x_coord, y_coord]

    #Draw moon
    set_background()
    waning_crescent((x_coord, y_coord), e_rad)
    disp.image(image, rotation)
    
    time.sleep(1)


while True:
    #Walk through next 24 hours
    for x, y, text in zip(az, alt, symbols):
        #Set coords
        y_coord = alt_to_y(y)
        x_coord = az_to_x(x)
        print(x)
        coord = [x_coord, y_coord]

        #Draw moon
        set_background()
        waning_crescent((x_coord, y_coord), e_rad)
        disp.image(image, rotation)
        
        time.sleep(1)

    #get clock time
    current_time = strftime("%Y-%m-%d %H:%M:%S")
    current_day = strftime("%Y/%m/%d")
    # print(current_time)
    print(current_day)
    
    moon.compute(current_day)
    moon_location = ephem.Equatorial(moon, epoch=ephem.J2000) #epoch is the celestial coordinate reference date. I just picked J2000

    # Example: observer location
    lat, lon = 40.7128, -74.0060  # New York City, TODO: get real latitude
    location = EarthLocation(lat=lat*u.deg, lon=lon*u.deg)

    # Time of observation
    t = Time(current_time)

    # GMST
    gmst = t.sidereal_time('mean', 'greenwich')
    # print(gmst)  # in hours

    # Local Sidereal Time
    lst = t.sidereal_time('mean', longitude=lon*u.deg)
    # print(lst)
    lst_hours = time_to_hours(str(lst))
    # print(lst_hours)

    # Example usage:
    lat = 40.7128 # NYC latitude TODO: figure out latitude

    # alt, az = alt_az(moon_location.ra, moon_location.dec, lat, lst_hours)
    # print(f"Altitude: {alt:.2f}, Azimuth: {az:.2f}")
    # print(f"RA: {moon_location.ra:.2f}, Dec: {moon_location.dec:.2f}")

    # y_coord = alt_to_y(alt)
    # x_coord = az_to_x(az)
    # coord = [x_coord, y_coord]
    # print(x_coord, y_coord)

    # #START DRAWING
    # # Draw a black filled box to clear the image.
    # draw.rectangle((0, 0, width, height), outline=0, fill=0)

    # #Draw horizon
    # draw_horizon()
    
    # #Draw clock
    # draw_clock()

    # #Draw moon with black halo for crossing horizon
    # moon_halo(coord)
    # waxing_crescent(coord, 2)
    

    
    
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
