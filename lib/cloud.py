#################################################################################
"""
OpenEO Module: Cloud Proxy Server


"""
#################################################################################
import logging, threading, socket,ssl,pprint
import urllib,re,json
import globalState,util
from lib.PluginSuperClass import PluginSuperClass

# logging for use in this module
_LOGGER = logging.getLogger(__name__)

   
#################################################################################
class cloudClassPlugin(PluginSuperClass):
    PRETTY_NAME = "OpenEO Cloud"
    CORE_PLUGIN = False # Can't be disabled from the UI
    
    pluginParamSpec={   "enabled":      {"type": "bool","default": True},
                        "authtoken":    {"type": "str","default":""},
                        "server":       {"type": "str","default":"ssl.openeo.uk"},
                        "port":         {"type": "int","default":8381}
                        }

    proxythread=None
    failurecount=0
    failuretime=None
    killflag=False

    def poll(self):
        self.killflag=False

        # Have we had too many failures? - if so, we should probably autodisable
        if self.failurecount>20:
            globalState.configDB.set("cloud","enabled",False)
            pass
        else:
            # Check to see if we are running a thread, and if we are supposed to be
            if self.pluginConfig["enabled"] and (self.proxythread is None or not self.proxythread.is_alive()):
                # Enabled, ut not running, so best we try starting
                self._thread_start()
                pass
            elif not self.pluginConfig["enabled"] and (self.proxythread is not None and self.proxythread.is_alive()):
                # Not Enabled, but running, we should kill the thread
                self._thread_stop()
                pass
            else:
                # We are operating as expected, so should probably reset the failurecount
                self.failurecount=0
        return(0)

    def configure(self,configParam):
        # Run a poll(), just in case we have been switched on or off
        super().configure(configParam)
        self.failurecount=0
        self.poll()

    def _thread_start(self):
        print(f"Starting proxy thread")
        self.proxythread = threading.Thread(target=self._proxythread, name='_proxythread', daemon=True)
        self.proxythread.start()

    def _thread_stop(self):
        print(f"Stopping proxy thread")
        self.killflag=True


    def _proxythread(self):
        """Connect to a TCP socket with AUTH handshake and receive commands."""
        client_id=globalState.stateDict["eo_serial_number"]

        if client_id=="" or client_id is None:
            print(f"waiting for EO comms to be established {client_id}")
            return(0)

        try:
            print(f"Connecting to {self.pluginConfig['server']}:{self.pluginConfig['port']}...")
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 30)
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 5)

            ssl_sock = ssl.wrap_socket(s)
            ssl_sock.connect((self.pluginConfig['server'], self.pluginConfig['port']))

            #print("Connected, keep-alive enabled.")
            f = ssl_sock.makefile('rw', encoding='utf-8', newline='\n')

            # Send AUTH
            connectionstr=f"AUTH {client_id} {self.pluginConfig['authtoken']} {globalState.appVer}\n"

            ssl_sock.sendall(bytearray(connectionstr,'utf-8'))

            # Wait for OK
            response=f.readline().rstrip('\n')
            if response != "OK":
                print(f"Client unauthorised. Cannot connect.")
                ssl_sock.close()
                # We need to back off, otherwise the server will ban us
                return(0)

            print("Authenticated with server.")

            # Command loop
            while True:
                if self.killflag:
                    self.failurecount+=1
                    return(0)

                command=f.readline().rstrip('\n')

                if command=="ACK":
                    # ACK message used for detecting dead connections
                    ssl_sock.sendall(bytearray(f"ACK\n",'utf-8'))
                else:
                    r=self.get_output(command)

                    for x in r['headers']:
                        (a,b)=x
                        ssl_sock.sendall(bytearray(f"HDR {a} {b}\n",'utf-8'))

                    ssl_sock.sendall(bytearray(f"LEN {r['bodylen']}\n",'utf-8'))
                    ssl_sock.sendall(r['body'])


        except Exception as e:
            print(f"Connection error: {e}")
            self.failurecount+=1

        finally:
            try:
                ssl_sock.close()
            except:
                pass
        self.failurecount+=1


    def get_output(self,command):

        returnval={}
        returnval["headers"]=""
        returnval["body"]=""
        returnval["bodylen"]=0

        print(f"command string=\"{command}\"")
        m = re.search('^(GET|POST) ([^ ]+) ?(.*)$', command)

        if not m:
            print(f"Malformed cloud command")
            return(returnval)

        method=m.group(1)
        URL="http://localhost"+m.group(2)

        match method:
            case "GET":
                response = urllib.request.urlopen(URL)
                returnval["headers"]=response.getheaders()
                returnval["body"] = response.read()
            case "POST":
                print(f"POST processing")
                data=m.group(3)
                print(f"POST processing values={data}")

                data = data.encode('ascii') # data should be bytes
                response = urllib.request.urlopen(URL,data)
                returnval["headers"]=response.getheaders()
                returnval["body"] = response.read()


        returnval["bodylen"]=len(returnval["body"])
        return(returnval)

    def get_user_settings(self):
        settings = []
        print("adding cloud settings")
        util.add_simple_setting(self.pluginConfig, settings, 'textinput', "cloud", ("authtoken",), f'Authorisation Code (Charger ID: {globalState.stateDict["eo_serial_number"]})',pattern='([A-Za-z0-9]{5})')
        return settings
