# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for
# full license information.

import time
import os
import sys
import asyncio
import threading
from azure.iot.device import IoTHubModuleClient

import json 
import serial
import micropyGPS
from scd30_i2c import SCD30

time.sleep(30)

gps = micropyGPS.MicropyGPS(9, 'dd')
scd30 = SCD30()

scd30.set_measurement_interval(2)
scd30.start_periodic_measurement()

# The client object is used to interact with your Azure IoT hub.
module_client = IoTHubModuleClient.create_from_edge_environment()

# connect the client.
module_client.connect()

def rungps(): # GPSモジュールを読み、GPSオブジェクトを更新する
        s = serial.Serial('/dev/serial0', 9600, timeout=10)
        s.readline() # 最初の1行は中途半端なデーターが読めることがあるので、捨てる
        while True:
                sentence = s.readline().decode('utf-8') # GPSデーターを読み、文字列に変換する
                if sentence[0] != '$': # 先頭が'$'でなければ捨てる
                        continue
                for x in sentence: # 読んだ文字列を解析してGPSオブジェクトにデーターを追加、更新する
                        gps.update(x)

gpsthread = threading.Thread(target=rungps, args=()) # 上の関数を実行するスレッドを生成
gpsthread.daemon = True
gpsthread.start() # スレッドを起動

while True:
        if gps.clean_sentences > 20: # ちゃんとしたデーターがある程度たまったら出力する
                h = gps.timestamp[0] if gps.timestamp[0] < 24 else gps.timestamp[0] - 24
                print('%2d:%02d:%04.1f' % (h, gps.timestamp[1], gps.timestamp[2]))
                print('緯度経度: %2.8f, %2.8f' % (gps.latitude[0], gps.longitude[0]))
                print('海抜: %f' % gps.altitude)
                print(gps.satellites_used)
                print('衛星番号: (仰角, 方位角, SN比)')
                for k, v in gps.satellite_data.items():
                        print('%d: %s' % (k, v))
                print('')

        if scd30.get_data_ready():
                m = scd30.read_measurement()
                if m is not None:                             
                        print(f"CO2: {m[0]:.2f}ppm, temp: {m[1]:.2f}'C, rh: {m[2]:.2f}%")

                        print('')

                        msg={
                                "temperature": m[1],
                                "humidity": m[2],
                                "co2": m[0],
                                "tracking": {
                                        "lat": gps.latitude[0],
                                        "lon": gps.longitude[0],
                                        "alt": gps.altitude
                                        }
                                }

                        module_client.send_message_to_output(json.dumps(msg),"output1")
                        
                        time.sleep(60)
                else:
                        time.sleep(0.2)