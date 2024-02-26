#!/usr/bin/env python

import dash
import dash_core_components as dcc
import dash_html_components as html
import dash_daq as daq
import dash_bootstrap_components as dbc
import rospy
from dash.dependencies import Input, Output, State
from multiprocessing import Process, Manager
import json
from std_srvs.srv import Trigger, TriggerRequest
import os
from std_msgs.msg import String, Int16, Float32
from sensor_msgs.msg import BatteryState, Range, Temperature

from flask import Flask, Response
import cv2

#create data structures for sharing variables between ROS process and Dash process
manager = Manager()
shared_dict = manager.dict()

#initialize shared data structure to zeroes
shared_dict["GAUGE_1"] = 0
shared_dict["GAUGE_2"] = 0
shared_dict["GAUGE_3"] = 0
shared_dict["GAUGE_4"] = 0

shared_dict["GAUGE_6"] = 0
shared_dict["GAUGE_7"] = 0
shared_dict["GAUGE_8"] = 0

#Video
'''
class VideoCamera(object):
    def __init__(self):
        self.video = cv2.VideoCapture(0)

    def __del__(self):
        self.video.release()

    def get_frame(self):
        success, image = self.video.read()
        ret, jpeg = cv2.imencode('.jpg', image)
        return jpeg.tobytes()


def gen(camera):
    while True:
        frame = camera.get_frame()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')

server = Flask(__name__)
#app = dash.Dash(__name__, server=server)

@server.route('/video_feed')
def video_feed():
    return Response(gen(VideoCamera()),
                    mimetype='multipart/x-mixed-replace; boundary=frame')
#..................................................................................
'''
#global service clients for button pushes (send a ROS service TriggeRequest upon button push)
button_1_trigger_service_client = None
button_2_trigger_service_client = None
button_3_trigger_service_client = None

#Initialize Dash app
# app = dash.Dash(external_stylesheets=[dbc.themes.BOOTSTRAP], title='ROS Dashboard',update_title= None,server=server)
app = dash.Dash(external_stylesheets=[dbc.themes.BOOTSTRAP], title='ROS Dashboard',update_title= None)


# Fast rate callback for the fast gauges (small and large)
#   -takes the ROS data as input (now in json format) and writes it as each gauge's value
#   -implemented as a javascript clientside callback to increase speed on SBC devices (raspberry pi)
app.clientside_callback(
    """
    function(n_intervals,json_data) {
        var obj = JSON.parse(json_data);
        if (obj) {
            return [parseInt(obj.GAUGE_1), parseInt(obj.GAUGE_2), parseInt(obj.GAUGE_3),parseInt(obj.GAUGE_4)];
        }
        else {
            return [0,0,0,0];
        }
    }
    """,
    [
    Output('progress-gauge1', 'value'),
    Output('progress-gauge2', 'value'),
    Output('progress-gauge3', 'value'),
    Output('darktheme-daq-gauge1', 'value'),
    ],
    Input('interval-component-fast', 'n_intervals'),
    State('intermediate-value', 'children')
)


# Medium rate callback for the thick, meter gauges
#   -takes the ROS data as input (now in json format) and writes it as each meter's value
#   -implemented as a javascript clientside callback to increase speed on SBC devices (raspberry pi)
app.clientside_callback(
    """
    function(n_intervals, json_data) {
        var obj = JSON.parse(json_data);
        if (obj) {
            return [parseInt(obj.GAUGE_6), parseInt(obj.GAUGE_7), parseInt(obj.GAUGE_8)];
        }
        else {
            return [0,0,0];
        }
    }
    """,
    [
    Output('darktheme-daq-tank1', 'value'),
    Output('darktheme-daq-tank2', 'value'),
    Output('darktheme-daq-tank3', 'value'),
    ],
    Input('interval-component-medium', 'n_intervals'),
    State('intermediate-value', 'children')
)


# callback that dispatches button clicks and sends a trigger request to the corresponding ROS service mapped to a button
@app.callback(
    Output("button-click-sinkhole", "children"),
    [Input("button_1", "n_clicks"),
     Input("button_2", "n_clicks"),
     Input("button_3", "n_clicks")]
)
def on_button_click(btn1, btn2, btn3):
    global button_1_trigger_service_client
    global button_2_trigger_service_client
    global button_3_trigger_service_client

    ctx = dash.callback_context

    if not ctx.triggered:
        print("initialized button...")
    else:
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        print("button clicked", button_id)

        button_trigger_request = TriggerRequest()
        try:
            if button_id == "button_1":
                response = button_1_trigger_service_client(button_trigger_request)
            elif button_id == "button_2":
                response = button_2_trigger_service_client(button_trigger_request)
            elif button_id == "button_3":
                response = button_3_trigger_service_client(button_trigger_request)
            else:
                response = None
                print("Couldn't map this button_id to a known button name: ", button_id)
            print("service response: ", response)
        except rospy.ServiceException as exc:
            print("Service did not process request: " + str(exc))
        return None


#Fast callback to take the ROS data dictionary and store it in json format (
#  -the json format is needed for the clientside javascript callbacks that do the fast clientside drawing of the widgets
@app.callback(
    Output('intermediate-value', 'children'),
    Input('interval-component-ros', 'n_intervals')
)

def fast_ros_dict_to_json( n_intervals ): 
    return json.dumps( dict(shared_dict))

def callback1(data): shared_dict["GAUGE_1"] = getattr(data, 'current')
def callback2(data): shared_dict["GAUGE_2"] = data.data
def callback3(data): shared_dict["GAUGE_3"] = data.data
def callback4(data): shared_dict["GAUGE_4"] = getattr(data, 'voltage')
def callback5(data): shared_dict["GAUGE_5"] = getattr(data, 'range')
def callback6(data): shared_dict["GAUGE_6"] = data.data
def callback7(data): shared_dict["GAUGE_7"] = getattr(data, 'temperature')
def callback8(data): shared_dict["GAUGE_8"] = data.data


# initialize subscribers to feed each visualization widget on the dashboard
def init_sub():
    rospy.init_node('ros_dashboard')
    rospy.Subscriber('/robot_stats/battery_load', BatteryState, callback1)
    rospy.Subscriber('/robot_stats/radio', Float32, callback2)
    rospy.Subscriber('/robot_stats/cpu_load', Float32, callback3)
    rospy.Subscriber('/robot_stats/battery', BatteryState, callback4)
    rospy.Subscriber('/robot_stats/communication', Range, callback5)
    rospy.Subscriber('/robot_stats/location', Float32, callback6)
    rospy.Subscriber('/robot_stats/temperature', Temperature, callback7)
    rospy.Subscriber('/robot_stats/communication_latency', Float32, callback8)
    rospy.spin()

#initialize a ROS service client for each button inside the Dash process
def init_button_service_clients():
    global button_1_trigger_service_client
    global button_2_trigger_service_client
    global button_3_trigger_service_client

    button_1_trigger_service_client = rospy.ServiceProxy('/robot_services/on_off_toggle', Trigger)
    button_2_trigger_service_client = rospy.ServiceProxy('/robot_services/estop', Trigger)
    button_3_trigger_service_client = rospy.ServiceProxy('/robot_services/calibrate', Trigger)


#Setup the layout of the dashboard.  3 buttons, 3 small fast gauges, 2 large fast gauges, and 3 thick slow meters
def setup_dash_app():

    theme = {
        'dark': True,
        'detail': '#007439',
        'primary': '#00EA64',
        'secondary': '#6E6E6E',
    }

    row = html.Div(
        [dbc.Row([
                  dbc.Col(dbc.Button('Power', block=True, id="button_1", color="success", size="lg", className="mr-1"), width=3) ,
                  dbc.Col(dbc.Button('E-Stop', block=True, id="button_2", color="danger", size="lg", className="mr-1"), width=3) ,
                  dbc.Col(dbc.Button('E-Calibrate', block=True, id="button_3", color="info", size="lg", className="mr-1"), width=3) ,
                 ],justify="center",align="center",),

                 html.Hr(),



         dbc.Row([
                #   dbc.Col(html.Img(src="/video_feed")),
                  dbc.Col(html.Img(src="http://10.0.0.39:8080/stream?topic=image_raw")),
                  dbc.Col([
                           dbc.Row(daq.Gauge(id="progress-gauge1",min = 0,max = 200, showCurrentValue = True,
                                             label = {'label': None,'style': {'font-size': '25px',"color": "#8dd7f9"}},
                                             units='Current', size=120)),
                           dbc.Row(daq.Gauge(id="progress-gauge2",min = 0,max = 100, showCurrentValue = True,
                                             label = {'label': None,'style': {'font-size': '25px',"color": "#8dd7f9"}},
                                             units='dBm', size=120)),
                           dbc.Row(daq.Gauge(id="progress-gauge3",min = 0,max = 150, showCurrentValue = True,
                                             label = {'label': None,'style': {'font-size': '25px',"color": "#8dd7f9"}},
                                             units='Average', size=120)),
                           dbc.Row(daq.Gauge(color=theme['primary'],id='darktheme-daq-gauge1',className='dark-theme-control',
                                             min = 0, max = 200, showCurrentValue=True,  
                                             label = {'label': None,'style': {'font-size': '25px',"color": "#8dd7f9"}},
                                             units='', size=120)),                                    
                           ],align="center"),
                 ],align="center",),

         dbc.Row([
                  dbc.Col(daq.Tank(id='darktheme-daq-tank1',className='dark-theme-control',style={'margin-left': '18px'},
                                   min=0,max=100,showCurrentValue=True,
                                   label = {'label': 'GPS Fix','style': {'font-size': '25px',"color": "#8dd7f9"}},
                                   units='GPS Sats')),
                  dbc.Col(daq.Tank(id='darktheme-daq-tank2',className='dark-theme-control',style={'margin-left': '18px'},
                                   min=0,max=200,showCurrentValue=True,
                                   label = {'label': 'Motor Temp','style': {'font-size': '25px',"color": "#8dd7f9"}},
                                   units='Degrees F')),
                  dbc.Col(daq.Tank(id='darktheme-daq-tank3',className='dark-theme-control',style={'margin-left': '18px'},
                                   min=0,max=100,showCurrentValue=True,
                                   label = {'label': 'Net Latency','style': {'font-size': '25px',"color": "#8dd7f9"}},
                                   units='ms')),
                 ],align="center",),

         # Hidden div inside the app that stores the intermediate value.  This is used for clientside callback
         html.Div(id='intermediate-value', style={'display': 'none'}),

         # Hidden div that just acts as a sinkhole.  Each callback is required to have an output
         html.Div(id='button-click-sinkhole', style={'display': 'none'}),
        ]
    )


    app.layout = dbc.Container(children=[daq.DarkThemeProvider(theme=theme, children=[row,
                               dcc.Interval(id='interval-component-fast',interval=100,n_intervals=0),
                               dcc.Interval(id='interval-component-medium',interval=2000,n_intervals=0),
                               dcc.Interval(id='interval-component-ros',interval=100,n_intervals=0),])],
                               style={'backgroundColor': '#303030','margin-top': '25px' },)


if __name__ == '__main__':
    print("Starting ROS Dashboard")
    setup_dash_app()
    p = Process(target=init_sub, args=())
    p.start()
    init_button_service_clients()
    app.run_server(host="0.0.0.0", debug=False, port=8050,  threaded=True)
