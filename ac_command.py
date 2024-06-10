# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0.

from awscrt import mqtt, http
from awsiot import mqtt_connection_builder
import sys
import threading
import time
import re
import json
import speech_recognition as sr
from utils.command_line_utils import CommandLineUtils



import pyttsx3


def speak(text):
    engine = pyttsx3.init()
    engine.setProperty('rate', 160)
    engine.setProperty('voice', "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech\Voices\Tokens\TTS_MS_EN-US_ZIRA_11.0")
    engine.say(text)
    engine.runAndWait()



state="off"
mode="cool"
temperature=24
swing="off"

commands=["mode","temperature","swing"]
command_operations={
    "state":["on","off"],
    "mode":["cool","fan","auto"],
    "temperature":["increase","decrease","reset","normal","set"],
    "swing":["on","off","toggle"]
}

components={"state":state,"mode":mode,"temperature":temperature,"swing":swing}
alternatives={
    "mode":"mode",
    "automatic":"auto",
    "reduce":"decrease",
    "add":"increase",
    "sum":"increase",
    "some":"increase",
    "dont":"off",
    "do not":"off",
    "don't":"off",
    "chill":"cool",
    "start":"on",
    "stop":"off",
}

def recognize_speech():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening...")
        recognizer.adjust_for_ambient_noise(source)
        audio_data = recognizer.listen(source)

        print("Processing...")

        try:
            text = recognizer.recognize_google(audio_data)
            qt=text
            if "echo" in text.lower() or "eco" in text.lower() or "ko" in text.lower()  or "eko" in text.lower() or "blue" in text.lower() or "ek" in text.lower():
                print("\033[H\033[J", end="")
                print("\n\n\t\tEcho is ACTIVE...\n\n")
                print("\t \t"+qt+"\n")
                return split_sentence(text)
            else:
                print("\033[H\033[J", end="")
                print("\n\n\t\tEcho is ACTIVE...\n\n")
                # print("\nEcho word missed\n not commanded to me\n"+text+"\n")
                print(".....")
                return recognize_speech()
        except sr.UnknownValueError:
            print("\033[H\033[J", end="")
            print("\n\n\t\tEcho is ACTIVE...\n\n")
            print("...")
            return recognize_speech()
        except sr.RequestError as e:
            print("Could not request results from Google Speech Recognition service; {0}".format(e))
            print("Restart the program")



# ----------------------------------- UTILITY FUNCTIONS---------------------------------------#
def split_sentence(sentence):
    pattern = r'\s*(?:and|or|also|with)\s*[,;]*'
    subsentences = re.split(pattern, sentence)
    subsentences = [sub.strip() for sub in subsentences if sub.strip()]
    print (subsentences)
    return identify_components(subsentences)



# ----------------------------------- UTILITY FUNCTIONS---------------------------------------#
# number finder functions

def number_in_sentence(sentence):
    pattern = r'\d+'
    numbers = re.findall(pattern, sentence)
    if len(numbers)==0:
        return None
    return int(numbers[0])


#ALEXA SKILLS AI for Rephrasing the sentence and identifying the components
def rephrase(sen):
    fin=[]
    for sentence in sen:
        for key,value in alternatives.items():
            if key in sentence:
                sentence=sentence.replace(key,value)
        fin.append(sentence)
    return fin



#--------------------------------------Utility functions ends----------------------------#
#               AI FUNCTIONS

def identify_components(sentence):
    speech=[]
    # print("Original: ",sentence)
    sentence=rephrase(sentence)
    # print("Rephrased: ",sentence)
    for sen in sentence:
        words = sen.lower().split()
        current_component = "state"
        current_component_operations=None
        for opr in commands:
            if opr in words:
                current_component = opr
                break
        
        for opr in command_operations[current_component]:
            if opr in words:
                current_component_operations = opr
                break
        # print("Before: ",current_component,current_component_operations)


        print(current_component,current_component_operations)
        # ALLOCATOR 
        if current_component=="state":
            if current_component_operations==None:
                components["state"]="on"
                speech.append("Power on")
            else:
                components["state"]=current_component_operations.lower()
                speech.append("Power "+current_component_operations)
        elif current_component=="swing":
            if current_component_operations==None:
                components["swing"]="on"
            else:
                components["swing"]=current_component_operations.lower()
            speech.append("Swing is "+components["swing"])
        elif current_component=="temperature":
            if number_in_sentence(sen)!=None:
                components["temperature"]=number_in_sentence(sen)
                speech.append("Temperature set to "+str(components["temperature"]))
            elif current_component_operations=="increase":
                components["temperature"]+=1
                speech.append("Temperature set to "+str(components["temperature"]))
            elif current_component_operations=="decrease":
                components["temperature"]-=1
                speech.append("Temperature set to "+str(components["temperature"]))
            else:
                components["temperature"]=24
                speech.append("Temperature set to "+str(components["temperature"]))
            if components["temperature"]>30:
                print("\n\n\tTemperature is too high and set to 30")
                speech.append("Temperature is too high and set to 30")
                components["temperature"]=30
            elif components["temperature"]<16:
                print("\n\n\tTemperature is too low  and set to 16")
                speech.append("Temperature is too low and set to 16")
                components["temperature"]=16
            
        else:
            if current_component_operations==None:
                print("\n\t  Please Speak clearly .\n",sen)
                speak("Please Speak clearly")
                return recognize_speech()
            components[current_component]=current_component_operations
            speech.append(current_component+" set to "+current_component_operations)
    speech=" and ".join(speech)
    # for key,value in components.items():
    #     print(key,value,sep=" - ")
    print("\n\n",speech,"\n\n")
    return [components,speech]
        


# AI ENDS HERE alexa 



cmdData = CommandLineUtils.parse_sample_input_pubsub()

received_count = 0
received_all_event = threading.Event()

# Callback when connection is accidentally lost.
def on_connection_interrupted(connection, error, **kwargs):
    print("Connection interrupted. error: {}".format(error))


# Callback when an interrupted connection is re-established.
def on_connection_resumed(connection, return_code, session_present, **kwargs):
    print("Connection resumed. return_code: {} session_present: {}".format(return_code, session_present))

    if return_code == mqtt.ConnectReturnCode.ACCEPTED and not session_present:
        print("Session did not persist. Resubscribing to existing topics...")
        resubscribe_future, _ = connection.resubscribe_existing_topics()

        # Cannot synchronously wait for resubscribe result because we're on the connection's event-loop thread,
        # evaluate result with a callback instead.
        resubscribe_future.add_done_callback(on_resubscribe_complete)


def on_resubscribe_complete(resubscribe_future):
    resubscribe_results = resubscribe_future.result()
    print("Resubscribe results: {}".format(resubscribe_results))

    for topic, qos in resubscribe_results['topics']:
        if qos is None:
            sys.exit("Server rejected resubscribe to topic: {}".format(topic))


# Callback when the subscribed topic receives a message
def on_message_received(topic, payload, dup, qos, retain, **kwargs):
    # print("\nReceived message from topic '{}'\n\t message :: {}\n".format(topic, payload))
    global received_count
    received_count += 1
    if received_count == cmdData.input_count:
        received_all_event.set()

# Callback when the connection successfully connects
def on_connection_success(connection, callback_data):
    assert isinstance(callback_data, mqtt.OnConnectionSuccessData)
    print("Connection Successful with return code: {} session present: {}".format(callback_data.return_code, callback_data.session_present))

# Callback when a connection attempt fails
def on_connection_failure(connection, callback_data):
    assert isinstance(callback_data, mqtt.OnConnectionFailureData)
    print("Connection failed with error code: {}".format(callback_data.error))

# Callback when a connection has been disconnected or shutdown successfully
def on_connection_closed(connection, callback_data):
    print("Connection closed")

if __name__ == '__main__':
    # Create the proxy options if the data is present in cmdData
    proxy_options = None
    if cmdData.input_proxy_host is not None and cmdData.input_proxy_port != 0:
        proxy_options = http.HttpProxyOptions(
            host_name=cmdData.input_proxy_host,
            port=cmdData.input_proxy_port)

    # Create a MQTT connection from the command line data
    mqtt_connection = mqtt_connection_builder.mtls_from_path(
        endpoint=cmdData.input_endpoint,
        port=cmdData.input_port,
        cert_filepath=cmdData.input_cert,
        pri_key_filepath=cmdData.input_key,
        ca_filepath=cmdData.input_ca,
        on_connection_interrupted=on_connection_interrupted,
        on_connection_resumed=on_connection_resumed,
        client_id=cmdData.input_clientId,
        clean_session=False,
        keep_alive_secs=30,
        http_proxy_options=proxy_options,
        on_connection_success=on_connection_success,
        on_connection_failure=on_connection_failure,
        on_connection_closed=on_connection_closed)

    if not cmdData.input_is_ci:
        print(f"Connecting to {cmdData.input_endpoint} with client ID '{cmdData.input_clientId}'...")
    else:
        print("Connecting to endpoint with client ID")
    connect_future = mqtt_connection.connect()

    # Future.result() waits until a result is available
    connect_future.result()
    print("Connected!")

    message_count = cmdData.input_count
    message_topic = cmdData.input_topic
    message_string = cmdData.input_message

    # Subscribe
    print("Subscribing to topic '{}'...".format(message_topic))
    subscribe_future, packet_id = mqtt_connection.subscribe(
        topic=message_topic,
        qos=mqtt.QoS.AT_LEAST_ONCE,
        callback=on_message_received)

    subscribe_result = subscribe_future.result()
    print("Subscribed with {}".format(str(subscribe_result['qos'])))
    print("\033[H\033[J", end="")

    # Publish message to server desired number of times.
    # This step is skipped if message is blank.
    # This step loops forever if count was set to 0.
    if message_string:
        if message_count == 0:
            print("\n\n\t\tStarting the TCS Online Internship Project...\n\n")
            print("\t  Echo The AI for your AC\n\n")
            speak("Echo at your service ")
        else:
            print("Sending {} message(s)".format(message_count))

        publish_count = 1
        while (publish_count <= message_count) or (message_count == 0):
            # message = "{} [{}]".format(message_string, publish_count)
            data=recognize_speech()
            message=data[0]
            print("\n\t\t"+data[1]+"\n")
            message_json = json.dumps(message)
            print("Publishing message to topic '{}'\n\t message ::\t {}\n".format(message_topic, message))
            mqtt_connection.publish(
                topic=message_topic,
                payload=message_json,
                qos=mqtt.QoS.AT_LEAST_ONCE)
            time.sleep(1)
            publish_count += 1
            speak(data[1]) 


    # Wait for all messages to be received.
    # This waits forever if count was set to 0.
    if message_count != 0 and not received_all_event.is_set():
        print("Waiting for all messages to be received...")

    received_all_event.wait()
    print("{} message(s) received.".format(received_count))

    # Disconnect
    print("Disconnecting...")
    disconnect_future = mqtt_connection.disconnect()
    disconnect_future.result()
    print("Disconnected!")
