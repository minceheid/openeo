#################################################################################
"""
OpenEO Module: Cloud Proxy Server


"""
#################################################################################
import logging, threading, socket,ssl,pprint
import urllib,re,json
import globalState,util
import traceback
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
    maxfailurecount=20
    failuretime=None
    killflag=False

    def poll(self):
        self.killflag=False

        # Have we had too many failures? - if so, we should probably autodisable
        if self.failurecount>self.maxfailurecount:
            globalState.configDB.set("cloud","enabled",False)
            self.failurecount=0
            _LOGGER.error(f"OpenEO Cloud - Given up connecting to server. Module disabled")
        else:
            # Check to see if we are running a thread, and if we are supposed to be
            if self.pluginConfig["enabled"] and (self.proxythread is None or not self.proxythread.is_alive()):
                # Enabled, but not running, so best we try starting
                self._thread_start()
                return(0)

            if not self.pluginConfig["enabled"] and (self.proxythread is not None and self.proxythread.is_alive()):
                # Not Enabled, but running, we should kill the thread
                self._thread_stop()
                return(0)
            
            # We are operating as expected, so should probably reset the failurecount
            # Using the following expression to try and work around a race condition. If a connection attempt
            # takes >5 seconds, we can come around for the next poll(), and think the session is established, and reset
            # the failurecount to 0. Instead, let's just decrement the failurecount if we think there is a sucessful 
            # connection.
            if (self.failurecount>0):
                self.failurecount-=1
                _LOGGER.warning(f"OpenEO Cloud - FailureCount decrement")

        return(0)

    def configure(self,configParam):
        # Run a poll(), just in case we have been switched on or off
        super().configure(configParam)
        self.failurecount=0
        self.poll()

    def _thread_start(self):
        _LOGGER.info(f"Starting OpenEO Cload thread")
        self.proxythread = threading.Thread(target=self._proxythread, name='_proxythread', daemon=True)
        self.proxythread.start()

    def _thread_stop(self):
        _LOGGER.info(f"Stopping OpenEO Cload thread")
        self.killflag=True


    def _proxythread(self):
        """Connect to a TCP socket with AUTH handshake and receive commands."""
        client_id=globalState.stateDict["eo_serial_number"]

        if client_id=="" or client_id is None:
            _LOGGER.warning(f"OpenEO Cloud - waiting for EO serial comms to be established for {client_id} before Cloud Connection can begin")
            return(0)
        
        if self.pluginConfig['authtoken']=="" or self.pluginConfig['authtoken'] is None:
            _LOGGER.warning(f"OpenEO Cloud module enabled, but authorisation token not defined in module settings. Not Connecting.")
            self.failurecount+=1
            return(0)

        try:
            _LOGGER.warning(f"OpenEO Cloud - Connecting to {self.pluginConfig['server']}:{self.pluginConfig['port']}. Attempt {self.failurecount}/{self.maxfailurecount}")

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
                _LOGGER.warning(f"OpenEO Cloud Connection unauthorised. Cannot connect.")
                ssl_sock.close()
                self.failurecount+=1
                # We need to back off, otherwise the server will ban us
                return(0)

            _LOGGER.warning(f"OpenEO Cloud Connection - Sucessfully Authorised.")


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
            _LOGGER.error(f"OpenEO Cloud Connection error: {e}")
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

        #print(f"command string=\"{command}\"")
        m = re.search('^(GET|POST) ([^ ]+) ?(.*)$', command)

        if not m:
            _LOGGER.error(f"OpenEO Cloud error: Malformed command {command}")

            return(returnval)

        method=m.group(1)
        URL="http://localhost"+m.group(2)

        match method:
            case "GET":
                response = urllib.request.urlopen(URL)
                returnval["headers"]=response.getheaders()
                returnval["body"] = response.read()
            case "POST":
                data=m.group(3)

                data = data.encode('ascii') # data should be bytes
                response = urllib.request.urlopen(URL,data)
                returnval["headers"]=response.getheaders()
                returnval["body"] = response.read()


        returnval["bodylen"]=len(returnval["body"])
        return(returnval)

    def get_user_settings(self):
        settings = []
        util.add_simple_setting(self.pluginConfig, settings, 'textinput', "cloud", ("authtoken",), f'Authorisation Code (Charger ID: {globalState.stateDict["eo_serial_number"]})',pattern='([A-Za-z0-9]{5})')
        return settings
