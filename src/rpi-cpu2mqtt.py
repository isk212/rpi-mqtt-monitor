# -*- coding: utf-8 -*-
# Python script (runs on 2 and 3) to check cpu load, cpu temperature and free space etc.
# on a Raspberry Pi or Ubuntu computer and publish the data to a MQTT server.
# RUN pip install paho-mqtt
# RUN sudo apt-get install python-pip

from __future__ import division
import subprocess
import time
import socket
import paho.mqtt.client as paho
import json
import config
import os

# get device host name - used in mqtt topic
hostname = socket.gethostname()


def check_used_space(path):
    st = os.statvfs(path)
    free_space = st.f_bavail * st.f_frsize
    total_space = st.f_blocks * st.f_frsize
    used_space = int(100 - ((free_space / total_space) * 100))
    return used_space


def check_cpu_load():
    # bash command to get cpu load from uptime command
    p = subprocess.Popen("uptime", shell=True, stdout=subprocess.PIPE).communicate()[0]
    cores = subprocess.Popen("nproc", shell=True, stdout=subprocess.PIPE).communicate()[0]
    cpu_load = str(p).split("average:")[1].split(", ")[0].replace(' ', '').replace(',', '.')
    cpu_load = float(cpu_load) / int(cores) * 100
    cpu_load = round(float(cpu_load), 1)
    return cpu_load


def check_voltage():
    try:
        full_cmd = "vcgencmd measure_volts | cut -f2 -d= | sed 's/000//'"
        voltage = subprocess.Popen(full_cmd, shell=True, stdout=subprocess.PIPE).communicate()[0]
        voltage = voltage.strip()[:-1]
    except Exception:
        voltage = 0
    return voltage


def check_swap():
    full_cmd = "free -t | awk 'NR == 3 {print $3/$2*100}'"
    swap = subprocess.Popen(full_cmd, shell=True, stdout=subprocess.PIPE).communicate()[0]
    swap = round(float(swap.decode("utf-8").replace(",", ".")), 1)
    return swap


def check_memory():
    full_cmd = "free -t | awk 'NR == 2 {print $3/$2*100}'"
    memory = subprocess.Popen(full_cmd, shell=True, stdout=subprocess.PIPE).communicate()[0]
    memory = round(float(memory.decode("utf-8").replace(",", ".")))
    return memory


def check_cpu_temp():
    full_cmd = "cat /sys/class/thermal/thermal_zone0/temp 2> /dev/null | sed 's/\(.\)..$//' | tail -n 1"
    try:
        p = subprocess.Popen(full_cmd, shell=True, stdout=subprocess.PIPE).communicate()[0]
        cpu_temp = p.decode("utf-8").replace('\n', ' ').replace('\r', '')
    except Exception:
        cpu_temp = 0
    return cpu_temp


def check_sys_clock_speed():
    full_cmd = "awk '{printf (\"%0.0f\",$1/1000); }' </sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq"
    return subprocess.Popen(full_cmd, shell=True, stdout=subprocess.PIPE).communicate()[0]


def check_uptime():
    full_cmd = "awk '{print int($1/3600/24)}' /proc/uptime"
    return int(subprocess.Popen(full_cmd, shell=True, stdout=subprocess.PIPE).communicate()[0])

def check_model_name():
   full_cmd = "cat /proc/cpuinfo | grep Model | sed 's/Model.*: //g'"
   return subprocess.Popen(full_cmd, shell=True, stdout=subprocess.PIPE).communicate()[0].decode("utf-8") 


def config_json(what_config):
    model_name = check_model_name()
    data = {
        "state_topic": "",
        "icon": "",
        "name": "",
        "unique_id": "",
        "unit_of_measurement": "",
	"device": {
	    "identifiers": [hostname],
	    "manufacturer": "Raspberry Pi",
	    "model": model_name,
	    "name": hostname
        }
    }

    data["state_topic"] = config.mqtt_topic_prefix + "/" + hostname
    if not config.group_messages: data["state_topic"] = data["state_topic"] + "/" + what_config
    data["unique_id"] = hostname + "_" + what_config
    if what_config == "cpuload":
        data["icon"] = "mdi:speedometer"
        data["name"] = hostname + " CPU Usage"
        data["unit_of_measurement"] = "%"
        if config.group_messages: data["value_template"] = "{{value_json.cpu_load}}"
    elif what_config == "cputemp":
        data["icon"] = "hass:thermometer"
        data["name"] = hostname + " CPU Temperature"
        data["unit_of_measurement"] = "°C"
        if config.group_messages: data["value_template"] = "{{value_json.cpu_temp}}" 
    elif what_config == "diskusage":
        data["icon"] = "mdi:harddisk"
        data["name"] = hostname + " Disk Usage"
        data["unit_of_measurement"] = "%"
        if config.group_messages: data["value_template"] = "{{value_json.used_space}}" 
    elif what_config == "voltage":
        data["icon"] = "mdi:speedometer"
        data["name"] = hostname + " CPU Voltage"
        data["unit_of_measurement"] = "V"
        if config.group_messages: data["value_template"] = "{{value_json.voltage}}" 
    elif what_config == "swap":
        data["icon"] = "mdi:harddisk"
        data["name"] = hostname + " Disk Swap"
        data["unit_of_measurement"] = "%"
        if config.group_messages: data["value_template"] = "{{value_json.swap}}" 
    elif what_config == "memory":
        data["icon"] = "mdi:memory"
        data["name"] = hostname + " Memory Usage"
        data["unit_of_measurement"] = "%"
        if config.group_messages: data["value_template"] = "{{value_json.memory}}" 
    elif what_config == "sys_clock_speed":
        data["icon"] = "mdi:speedometer"
        data["name"] = hostname + " CPU Clock Speed"
        data["unit_of_measurement"] = "MHz"
        if config.group_messages: data["value_template"] = "{{value_json.sys_clock_speed}}" 
    elif what_config == "uptime_days":
        data["icon"] = "mdi:timer"
        data["name"] = hostname + " Uptime"
        data["unit_of_measurement"] = "days"
        if config.group_messages: data["value_template"] = "{{value_json.uptime_days}}" 
    else:
        return ""
    # Return our built discovery config
    return json.dumps(data)


def publish_to_mqtt(cpu_load=0, cpu_temp=0, used_space=0, voltage=0, sys_clock_speed=0, swap=0, memory=0,
                    uptime_days=0):
    # connect to mqtt server
    client = paho.Client()
    client.username_pw_set(config.mqtt_user, config.mqtt_password)
    client.connect(config.mqtt_host, int(config.mqtt_port))

    # publish monitored values to MQTT
    if config.cpu_load:
        if config.discovery_messages:
            client.publish("homeassistant/sensor/" + config.mqtt_topic_prefix + "/" + hostname + "_cpuload/config",
                           config_json('cpuload'), qos=0)
            time.sleep(config.sleep_time)
        client.publish(config.mqtt_topic_prefix + "/" + hostname + "/cpuload", cpu_load, qos=1)
        time.sleep(config.sleep_time)
    if config.cpu_temp:
        if config.discovery_messages:
            client.publish("homeassistant/sensor/" + config.mqtt_topic_prefix + "/" + hostname + "_cputemp/config",
                           config_json('cputemp'), qos=0)
            time.sleep(config.sleep_time)
        client.publish(config.mqtt_topic_prefix + "/" + hostname + "/cputemp", cpu_temp, qos=1)
        time.sleep(config.sleep_time)
    if config.used_space:
        if config.discovery_messages:
            client.publish("homeassistant/sensor/" + config.mqtt_topic_prefix + "/" + hostname + "_diskusage/config",
                           config_json('diskusage'), qos=0)
            time.sleep(config.sleep_time)
        client.publish(config.mqtt_topic_prefix + "/" + hostname + "/diskusage", used_space, qos=1)
        time.sleep(config.sleep_time)
    if config.voltage:
        if config.discovery_messages:
            client.publish("homeassistant/sensor/" + config.mqtt_topic_prefix + "/" + hostname + "_voltage/config",
                           config_json('voltage'), qos=0)
            time.sleep(config.sleep_time)
        client.publish(config.mqtt_topic_prefix + "/" + hostname + "/voltage", voltage, qos=1)
        time.sleep(config.sleep_time)
    if config.swap:
        if config.discovery_messages:
            client.publish("homeassistant/sensor/" + config.mqtt_topic_prefix + "/" + hostname + "_swap/config",
                           config_json('swap'), qos=0)
            time.sleep(config.sleep_time)
        client.publish(config.mqtt_topic_prefix + "/" + hostname + "/swap", swap, qos=1)
        time.sleep(config.sleep_time)
    if config.memory:
        if config.discovery_messages:
            client.publish("homeassistant/sensor/" + config.mqtt_topic_prefix + "/" + hostname + "_memory/config",
                           config_json('memory'), qos=0)
            time.sleep(config.sleep_time)
        client.publish(config.mqtt_topic_prefix + "/" + hostname + "/memory", memory, qos=1)
        time.sleep(config.sleep_time)
    if config.sys_clock_speed:
        if config.discovery_messages:
            client.publish(
                "homeassistant/sensor/" + config.mqtt_topic_prefix + "/" + hostname + "_sys_clock_speed/config",
                config_json('sys_clock_speed'), qos=0)
            time.sleep(config.sleep_time)
        client.publish(config.mqtt_topic_prefix + "/" + hostname + "/sys_clock_speed", sys_clock_speed, qos=1)
        time.sleep(config.sleep_time)
    if config.uptime:
        if config.discovery_messages:
            client.publish("homeassistant/sensor/" + config.mqtt_topic_prefix + "/" + hostname + "_uptime_days/config",
                           config_json('uptime_days'), qos=0)
            time.sleep(config.sleep_time)
        client.publish(config.mqtt_topic_prefix + "/" + hostname + "/uptime_days", uptime_days, qos=1)
        time.sleep(config.sleep_time)
    # disconnect from mqtt server
    client.disconnect()


def bulk_publish_to_mqtt(cpu_load=0, cpu_temp=0, used_space=0, voltage=0, sys_clock_speed=0, swap=0, memory=0,
                         uptime_days=0):
    # compose the CSV message containing the measured values

    #values = cpu_load, float(cpu_temp), used_space, float(voltage), int(sys_clock_speed), swap, memory, uptime_days
    #values = str(values)[1:-1]

    values = {
            "cpu_load":cpu_load,
            "cpu_temp":float(cpu_temp),
            "used_space":used_space,
            "voltage":float(voltage),
            "sys_clock_speed":int(sys_clock_speed),
            "swap":swap,
            "memory":memory,
            "uptime_days":uptime_days
            }
    values_json = json.dumps(values)

    # connect to mqtt server
    client = paho.Client()
    client.username_pw_set(config.mqtt_user, config.mqtt_password)
    client.connect(config.mqtt_host, int(config.mqtt_port))

    configs_enabled=[]
    if config.cpu_load: configs_enabled.append("cpuload")
    if config.cpu_temp: configs_enabled.append("cputemp")
    if config.used_space: configs_enabled.append("diskusage")
    if config.voltage: configs_enabled.append("voltage")
    if config.sys_clock_speed: configs_enabled.append("sys_clock_speed")
    if config.swap: configs_enabled.append("swap")
    if config.memory: configs_enabled.append("memory")
    if config.uptime: configs_enabled.append("uptime_days")

    if config.discovery_messages:
        for c in configs_enabled:
            client.publish("homeassistant/sensor/"+config.mqtt_topic_prefix + "/" + hostname + "_"+c+"/config", config_json(c), qos=0)
            time.sleep(config.sleep_time)

    # publish monitored values to MQTT
    client.publish(config.mqtt_topic_prefix + "/" + hostname, values_json, qos=1)

    # disconnect from mqtt server
    client.disconnect()


if __name__ == '__main__':
    # set all monitored values to False in case they are turned off in the config
    cpu_load = cpu_temp = used_space = voltage = sys_clock_speed = swap = memory = uptime_days = False

    # delay the execution of the script
    time.sleep(config.random_delay)

    # collect the monitored values
    if config.cpu_load:
        cpu_load = check_cpu_load()
    if config.cpu_temp:
        cpu_temp = check_cpu_temp()
    if config.used_space:
        used_space = check_used_space('/')
    if config.voltage:
        voltage = check_voltage()
    if config.sys_clock_speed:
        sys_clock_speed = check_sys_clock_speed()
    if config.swap:
        swap = check_swap()
    if config.memory:
        memory = check_memory()
    if config.uptime:
        uptime_days = check_uptime()
    # Publish messages to MQTT
    if config.group_messages:
        bulk_publish_to_mqtt(cpu_load, cpu_temp, used_space, voltage, sys_clock_speed, swap, memory, uptime_days)
    else:
        publish_to_mqtt(cpu_load, cpu_temp, used_space, voltage, sys_clock_speed, swap, memory, uptime_days)
