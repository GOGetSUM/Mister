import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

import requests
import datetime as dt
import time as tt

import certifi
import ssl
import geopy.geocoders
from geopy.geocoders import Nominatim

from twilio.rest import Client

from tplinkcloud import TPLinkDeviceManager
import asyncio

from dotenv import load_dotenv


TEMP = 90 #in degrees
WEATHER_ID = 800 # clear skies no rain
RUN_TIME = 30 # in seconds
ADDRESS = os.environ.get("LOCATION")

# LOAD environment variables
load_dotenv(".env")

# Twilio --------------------------------------------------------------------------

def send_message():
    TWILIO_SID = os.environ.get('TWILIO_SID')
    TWILIO_AUTHTK = os.environ.get('TWILIO_AUTHTK')
    list_of_recipients = os.environ.get('recipients')
    MESSAGE = (['GoGetSum - Mister\n'
                '\nMister has been turned on for 30 seconds. It is now off.\n'
                '\n\tHave a wonderful day, stay cool!'])
    for recipient in list_of_recipients:
        client = Client(TWILIO_SID, TWILIO_AUTHTK)
        message = client.messages.create(
            body=MESSAGE,
            from_=os.environ.get('twilio'),
            to=recipient
        )


# KASA -------------------------------------------------------------------------------

username= os.environ.get('KASA_USER')
password=os.environ.get('KASA_PASSWORD')

device_manager = TPLinkDeviceManager(username,password)

async def turn_on_mister():
    device = await device_manager.find_device('Mister')
    await device.power_off()
    return print("Mister has been turned on")

async def turn_off_mister():
    device = await device_manager.find_device('Mister')
    await device.power_off()
    return print("Mister has been turned off")

async def is_off():
    device = await device_manager.find_device('Mister')
    res = await device.is_off()
    return res

#APP & DATABASE SETUP ---------------------------------------------------------------------------

app =Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///Weather.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PROPAGATE_EXCEPTIONS'] = True
db = SQLAlchemy(app)

app.secret_key= os.environ.get('keykeykey')


class WeatherModel(db.Model):
    __tablename__ = "Weather"
    id = db.Column(db.Integer,primary_key=True)
    date = db.Column(db.String(80), nullable=False)
    time= db.Column(db.String(80), nullable=False)
    current_temp = db.Column(db.Integer, nullable=False)
    feels_like_temp = db.Column(db.Integer, nullable=False)
    wind_speed = db.Column(db.Integer, nullable=False)
    weather_id = db.Column(db.Integer, nullable=False)
    weather_desc = db.Column(db.String(250), nullable=False)
    weather_main = db.Column(db.String(250), nullable=False)
    weather_icon = db.Column(db.String(250), nullable=False)
# db.create_all()

#Location generator-----can be pulled from KASA in later upgrade. -------------------------------------------------

ctx = ssl.create_default_context(cafile=certifi.where())
geopy.geocoders.options.default_ssl_context = ctx

geolocator = Nominatim(user_agent="LBCMIster")
location = geolocator.geocode(ADDRESS)

lat = location.latitude
lon = location.longitude
part = "currently"
API_key = os.environ.get('OWM_API_KEY')


#Open Weather call and request current information

OWM_Endpoint = "https://api.openweathermap.org/data/2.5/onecall"

weather_params = {
    "lat": lat,
    "lon": lon,
    "appid": API_key,
    "exclude": "hourly,minutely,daily",
    "units":"imperial",
}

response = requests.get(OWM_Endpoint,params=weather_params)
response.raise_for_status()
weather_data = response.json()

# Manipulate data, saved only required data

weather_slice = weather_data['current']
current_temp = weather_slice['temp']
feels_like_temp = weather_slice['feels_like']
wind_speed = weather_slice['wind_speed']
weather_desc = weather_slice['weather'][0]['description']
weather_id = weather_slice['weather'][0]['id']
weather_main = weather_slice['weather'][0]['main']
weather_icon = weather_slice['weather'][0]['icon']
dt_timestamp = weather_slice['dt'] + weather_data['timezone_offset']
timestamp = str(dt.datetime.utcfromtimestamp(dt_timestamp)).split(" ")
time = timestamp[1]
hour = int(time.split(":")[0])
minutes = int(time.split(":")[1])
date = timestamp[0]
latest_id = WeatherModel.query.order_by(WeatherModel.id.desc()).first()
new_id = latest_id.id + 1

weather_0 = WeatherModel(
    id=new_id,
    date=date,
    time=time,
    current_temp=current_temp,
    feels_like_temp=feels_like_temp,
    wind_speed=wind_speed,
    weather_id=weather_id,
    weather_desc=weather_desc,
    weather_main= weather_main,
    weather_icon= weather_icon,
)


#- LOGIC and Actuation of Mister--------------------------------------------------------
list = WeatherModel.query.order_by(WeatherModel.id.desc()).all()

first = list[0]

if time == first.time:
    print("Entry exist")
    pass

else:

    db.session.add(weather_0)
    db.session.commit()

    if first.feels_like_temp >= TEMP and first.weather_id >= WEATHER_ID:
        try:
            if asyncio.run(is_off()):
                asyncio.run(turn_on_mister())
                tt.sleep(RUN_TIME)
                asyncio.run(turn_off_mister())
                send_message()
            else:
                print('Mister is already running')
                asyncio.run(turn_off_mister())
        except:
            print('Something Went wrong')
    else:
        print("Mister is Off")



if __name__ == "__main__":
    app.run( debug=True)

