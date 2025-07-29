#################################################################################
"""
OpenEO Module: Config Server
Spawns a webserver thread which hosts the web interface for setting the timer 
schedule. Note that this will only ever update the first schedule in the scheduler
list of "on" periods for the charger.

I expect this module could be integrated to the webserver module to reduce the 
number of threads running.

Configuration example:
"configserver": {"port": 80}

"""
#################################################################################
import re, logging, threading, json, http.server, socketserver, datetime, socket, os, copy, numbers, urllib.parse
import globalState, util

# logging for use in this module
_LOGGER = logging.getLogger(__name__)

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape
env = Environment(
    loader=FileSystemLoader("lib/configserver/templates"),
    autoescape=select_autoescape()
)

template_to_name = {
    "home": "Charger Control",
    "settings" : "Settings",
    "stats" : "Statistics"
}

class SocketOptionTCPServer(socketserver.TCPServer):
    """This child class allows us to set the REUSEADDR and REUSEPORT options on the socket
    which means the Python task can be started and stopped without breaking the config server
    due to the previous socket being in TIME_WAIT."""
    def server_bind(self):
        # Set socket options before binding
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        super().server_bind()

#################################################################################
class configserverClassPlugin:
    pretty_name = "Config Server"
    CORE_PLUGIN = True # Can't be disabled from the UI
    
    pluginConfig = {}
    myName = ""

    def __str__(self):
        return self.myName

    def get_config(self):
        return self.pluginConfig
        
    def configure(self,configParam):
        _LOGGER.debug("Plugin Configured: "+self.myName)
        self.pluginConfig=configParam
        
    def poll(self):
        # Webserver should never need to influence the charger, I think
        # However - we must always return a zero value (zero amps)
        return 0

    def __init__(self,configParam):
        # Store the name of the plugin for reuse elsewhere
        self.myName=re.sub('ClassPlugin$','',type(self).__name__)
        _LOGGER.debug("Initialising Module: "+self.myName)

        self.pluginConfig["port"]=configParam.get("port",80)
        if (isinstance(self.pluginConfig["port"],(int))!=True):
            _LOGGER.error("Invalid port ({}) in {} plugin config in {}. Defaulting to 80".format(self.pluginConfig["port"],self.myName,globalState.stateDict["eo_config_file"]))
            self.pluginConfig["port"]=80

        serverthread = threading.Thread(target=self.webserver, name='serverthread')
        serverthread.start()

    def webserver(self):
        socketserver.TCPServer.allow_reuse_address = True
        with SocketOptionTCPServer(("", self.pluginConfig["port"]), self.CustomHandler) as httpd:
            _LOGGER.info("Serving Configuration webserver on port {}".format(self.pluginConfig["port"]))
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                httpd.shutdown()

    ###############
    # Everything from here down is the config handling

    class CustomHandler(http.server.BaseHTTPRequestHandler):
        config = {}
        _context = {}
        selected_page = ""

        # Load initial configuration
        def load_config(self):
            try:
                with open(globalState.stateDict["eo_config_file"], "r") as f:
                    self.config = json.load(f)
                    return True
            except (FileNotFoundError, ValueError):
                self.config = {}
                return False

        def save_config(self):
            with open(globalState.stateDict["eo_config_file"], "w") as f:
                f.write(json.dumps(self.config, indent=2))

        def do_GET(self):
            # handle the root page correctly
            if self.path == "/":
                self.path = "/home.html"
                
            ################################
            # Prometheus exporter
            if format(self.path)=="/metrics":
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()

                # Dump all global variables in prometheus exporter format
                for cfgkey,cfgvalue in globalState.stateDict.items():
                    if isinstance(cfgvalue, numbers.Number):
                        if (cfgkey=="eo_charger_state_id"):
                            self.wfile.write(str("# HELP "+cfgkey+" "+globalState.stateDict["eo_charger_state"]+"\n").encode('utf-8'))

                        self.wfile.write(str("# TYPE "+cfgkey+" gauge\n").encode('utf-8'))
                        self.wfile.write(str(cfgkey+"{} "+str(cfgvalue)+"\n").encode('utf-8'))   
                return

            ################################
            # Home Assistant
            if format(self.path)=="/api":
                status={}
                status["eo_charger_state"]={"id":globalState.stateDict["eo_charger_state_id"],"status":globalState.stateDict["eo_charger_state"]}
                for cfgkey,cfgvalue in globalState.stateDict.items():
                    if (cfgkey!="eo_harger_state_id") and (cfgkey!="eo_charger_state"):
                            status[cfgkey]=cfgvalue

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(status).encode('utf-8'))
                return


            ###################################################################
            ## expose the configuration from the config file to the api
            ## we can also use POST/setconfig to write the configuration
            if self.path == "/getconfig":
                with open(globalState.stateDict["eo_config_file"], "r") as f:
                    parsed_config = json.load(f)
                    self.send_response(200)
                    self.send_header("Content-type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(parsed_config).encode("utf-8"))
                    return
            
            ###################################################################
            ## expose the logger module metrics to the api, if that is available
            ## in cfg
            if re.search("^/getchartdata",self.path):
                # Only respond if the logger is active
                if "_dataLog" in globalState.stateDict:
                    query_components = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                    query_type = query_components.get('type', [''])[0]  # Default to empty string if not found
                    query_since = query_components.get('since', [''])[0]  # Default to empty string if not found
                    try:
                        query_since = datetime.datetime.strptime(query_since,"%Y-%m-%d %H:%M:%S.%f")
                    except ValueError:
                        query_since=None

                    self.send_response(200)
                    self.send_header("Content-type", "application/json")
                    self.end_headers()

                    if (query_type=="plotly"):
                        if (query_since==""):
                            self.wfile.write(json.dumps(globalState.stateDict["_dataLog"].get_plotly(),default=str).encode("utf-8"))
                            return
                        else:
                            self.wfile.write(json.dumps(globalState.stateDict["_dataLog"].get_plotly(query_since),default=str).encode("utf-8"))
                            return
                    else:
                        if (query_since==""):
                            self.wfile.write(json.dumps(globalState.stateDict["_dataLog"].get_data(),default=str).encode("utf-8"))
                            return
                        else:
                            self.wfile.write(json.dumps(globalState.stateDict["_dataLog"].get_data(query_since),default=str).encode("utf-8"))
                            return 

                else:
                    self.send_error(404, "Not Found")
                    return

            ###################################################################
            ## expose the running status to the api, as recorded in the global dict in cfg
            if self.path == "/getstatus":
                # copy is needed to avoid a RuntimeError due to this dict changing size
                # we can't deepcopy because in some cases the modules within cannot be pickled (e.g. thread objects)
                status = copy.copy(globalState.stateDict)
                for x in globalState.stateDict:
                    if x[0]=="_":
                        # an underscore denotes a private configuration that probably shouldn't be exposed
                        status.pop(x,None)

                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(status).encode("utf-8"))
                return
                
            #############
            # Revert to serving files from the filesystem
            # @TODO: not yet sure how I can have this CustomHandler class pick up self.myName from the parent
            # object, to remove this hardcoded subdirectory name
            self.path='lib/configserver' + self.path
            _LOGGER.debug("serving: " + self.path)
            
            # Try to prevent directory backtracking.  If we detect ".." in the URL, that's not allowed.
            if ".." in self.path:
                self.send_error(403, "Forbidden - but, nice try")
                return
                
            file, ext = os.path.splitext(self.path)
            ext = ext.lstrip('.')
            base = os.path.basename(file)
            _LOGGER.debug("file %s ext %s" % (file, ext))
            
            # HTML files are handled as templated objects.
            if ext.lower() == "html":
                # Setup the context according to the config (only for templated files)
                if base in template_to_name:
                    self.selected_page = template_to_name[base]
                self.load_config()
                self.set_context()
                
                try:
                    template = env.get_template(base + ".tpl")
                    self.send_response(200)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(template.render(self._context).encode("utf-8"))
                    return
                except TemplateNotFound as e:
                    _LOGGER.error("Failed to load template '%s': %r" % (base, e))
                    self.send_error(404, "Template Not Found")
                    return
            
            extension_to_mime_enc = {
                'ico' : ('image/icon', None),
                'png' : ('image/png', None),
                'svg' : ('image/svg+xml', 'utf-8'),
                'js' : ('text/javascript', 'utf-8'),
                'css' : ('text/css', 'utf-8'),
            }
            
            for k, v in extension_to_mime_enc.items():
                if ext.lower() == k:
                    # If encoding is None, open as binary file
                    mode = 'r'
                    if v[1] == None:
                        mode = 'rb'
                        
                    try:
                        with open(self.path, mode) as f:
                            self.send_response(200)
                            self.send_header("Content-type", v[0])
                            self.end_headers()
                            if v[1] != None:
                                self.wfile.write(f.read().encode(v[1]))
                            else:
                                self.wfile.write(f.read())
                            return
                    except FileNotFoundError:
                        self.send_error(404, "Not Found")
                        return
            
            # If we fell through, then no file was found
            self.send_error(404, "Not Found")
            return
        
        def merge(self,a: dict, b: dict, path=[]):
            """Recursive merge of dictionary/lists
            @TODO: More testing required. This might be buggy."""
            for key in b:
                if key in a:
                    if isinstance(a[key], dict) and isinstance(b[key], dict):
                        self.merge(a[key], b[key], path + [str(key)])
                    elif isinstance(a[key], list) and isinstance(b[key], list):
                        for i in range(len(b[key])):
                            self.merge(a[key][i], b[key][i], path+[str(i)])
                    elif a[key] != b[key]:
                        a[key] = b[key]
                else:
                    a[key] = b[key]
            return a            

        def do_POST(self):
            _LOGGER.info("do_POST(%s)" % self.path)
            
            if self.path == "/setconfig":
                ##################################
                # API for writing configuration. This allows an arbitrary length dict to be passed via JSON
                # and it will overwrite the running configuration, by merging any elements in the list into
                # the running configuration. Remember garbage in-garbage out! - also be aware that this is
                # not protected in any way, so anyone with access to the network could do damage to configuration
                # this isn't ideal, and we might need to put some guardrails in here
                content_length = int(self.headers['Content-Length'])
                post_data = json.loads(self.rfile.read(content_length).decode('utf-8'))

                print(post_data)
                if not "chargeroptions" in post_data:
                    post_data["chargeroptions"]={}
                post_data["chargeroptions"]["config_update_time"] = str(datetime.datetime.now())
                
                self.load_config()
                self.merge(self.config, post_data)
                _LOGGER.info('Merged config %r' % self.config)

                try:
                    self.save_config()

                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "success", "config": self.config}).encode("utf-8"))
                    _LOGGER.info('Config saved')
                    return
                except Exception as e:
                    _LOGGER.error("Unable to write to config file:"+globalState.stateDict["eo_config_file"],repr(e))
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "failed", "config" : self.config}).encode("utf-8"))
                    _LOGGER.info('Config save error: %r' % e)
                    return
            elif self.path == "/setmode":
                ##################################
                # API for changing the mode.  Depending upon the selected mode, one or more modules 
                # may be enabled or disabled at once.
                content_length = int(self.headers['Content-Length'])
                
                try:
                    post_data = json.loads(self.rfile.read(content_length).decode('utf-8'))
                    new_mode = str(post_data["newmode"]).lower().strip()
                    self.load_config()
                    
                    _LOGGER.info("Set mode request: '%s'" % new_mode)
                
                    if new_mode == "schedule":
                        # Disable all modules except the reserved ones
                        self.switch_modules(0)
                        # Enable the scheduler
                        self.config["scheduler"]["enabled"] = 1
                    elif new_mode == "manual":
                        # Disable all modules except the reserved ones
                        self.switch_modules(0)
                        # Enable the switch module
                        self.config["switch"]["enabled"] = 1
                    elif new_mode == "remote":
                        # Disable the switch & schedule module
                        self.config["scheduler"]["enabled"] = 0
                        self.config["switch"]["enabled"] = 0
                        # Enable all modules, don't touch the reserved ones.
                        self.switch_modules(1)
                    else:
                        raise RuntimeError("unsupported mode %s" % new_mode)
                        
                    # Save the mode string
                    if "chargeroptions" not in self.config:
                        self.config["chargeroptions"] = {}
                    self.config["chargeroptions"]["mode"] = new_mode
                    _LOGGER.info("New config: %s" % repr(self.config))
                    
                    # Sync to disk.  This is required to keep the scheduler up to date,
                    # which is probably a limitation that should be fixed eventually.
                    self.save_config()
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "success"}).encode("utf-8"))
                    return
                except Exception as e:
                    _LOGGER.error("Error passing mode request: %s" % repr(e))
                    self.send_error(500, "Error passing mode request: %s" % repr(e))
            else:
                _LOGGER.error("Unknown endpoint '%s'" % self.path)
                self.send_error(404, "Not Found")
                return

        def switch_modules(self, state):
            """Enable or disable all modules except reserved ones."""
            reserved = ["configserver", "webserver"]  # Future, this needs to come from the module parameters
            for key, item in self.config.items():
                if key not in reserved and not key.startswith("_"):
                    try:
                        _LOGGER.info("Trying to disable '%s'" % key)
                        self.config[key]["enabled"] = 0
                    except Exception as e:
                        _LOGGER.warning("Unable to toggle module '%s'" % key)
        
        def get_user_settings(self):
            """Called from the set_context method to update user settings."""
            settings = []
            util.add_simple_setting(settings, 'number', "configserver", ("port",), 'Port',
                note='Recommended port 80.  Changing the port number requires a restart of openeo.  Changing to an inaccessible or unsupported port may render the openeo interface unusable, so take care.', \
                range=(1,65535), step=1, default=80)
            return settings
            
        def set_context(self):
            """Update the jinja context according to the system state.  
            @TODO this should be cached as called on every load currently."""
            self._context = {
                "openeo_cfg" : self.config,
                "status" : globalState.stateDict,
                "settings" : [],
                "title" : self.selected_page
            } 
            
            # If a module supports exposing settings, add each.
            if "_moduleDict" in globalState.stateDict:
                for modulename, module in globalState.stateDict["_moduleDict"].items():
                    try:
                        mod_settings = []
                        if not module.CORE_PLUGIN:
                            util.add_simple_setting(self.config, mod_settings, 'boolean', module.myName, (module.myName, "enabled",), 'Enable Module') 
                        if hasattr(module, "get_user_settings"):
                            sets = module.get_user_settings()
                            if isinstance(sets, list) and len(sets) > 0:  # Might return None or some other garbage value.
                                mod_settings += sets
                                util.add_category_exit(mod_settings)
                        if len(mod_settings) > 0:
                            util.add_header_setting(self._context["settings"], module.PRETTY_NAME)
                            self._context["settings"] += mod_settings
                    except Exception as e:
                        _LOGGER.error("Exception generating settings for %r: %r" % (module, e))
