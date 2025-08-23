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
import re, logging, threading, json, http.server, socketserver, datetime, socket, os
import copy, time, numbers, urllib.parse, subprocess

import globalState, util
from lib.PluginSuperClass import PluginSuperClass

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

class ThreadedServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """This child class allows us to set the REUSEADDR and REUSEPORT options on the socket
    which means the Python task can be started and stopped without breaking the config server
    due to the previous socket being in TIME_WAIT.
    
    It's now threaded, allowing for multiple requests to be handled in parallel."""
    def server_bind(self):
        # Set socket options before binding
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        super().server_bind()
        
#################################################################################
class configserverClassPlugin(PluginSuperClass):
    pretty_name = "Config Server"
    CORE_PLUGIN = True # Can't be disabled from the UI
    
    pluginParamSpec={   "enabled":      {"type": "bool","default": True},
                        "port":  {"type": "int","default":80}}

    def __init__(self,configParam):
        super().__init__(configParam)

        serverthread = threading.Thread(target=self.webserver, name='serverthread')
        serverthread.start()

    def webserver(self):
        socketserver.TCPServer.allow_reuse_address = True
        with ThreadedServer(("", self.pluginConfig["port"]), self.CustomHandler) as httpd:
            _LOGGER.info("Serving Configuration webserver on port {}".format(self.pluginConfig["port"]))
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                httpd.shutdown()

    #################################################################################
    # Everything from here down is the config handling
    
    class CustomHandler(http.server.BaseHTTPRequestHandler):
        config = {}
        _context = {}
        selected_page = ""


        # Load initial configuration
        def load_config(self):
            ##self.config=globalState.configDB.dict()
            # We can't load config directly from sqlite, as we need the modules to interpret and typecast
            # the attributes, so instead, we need to recompile the full config from polling the plugin modules
            # There must be a better way...

            self.config={}
            for modulename,module in globalState.stateDict["_moduleDict"].items():
                    self.config[modulename]=module.pluginConfig

            return True
            

        def do_GET(self):
            ################################
            # Prometheus exporter
            if format(self.path)=="/metrics":
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()

                # Dump all global variables in prometheus exporter format
                for cfgkey,cfgvalue in globalState.stateDict.items():
                    if cfgkey[0]!="_":
                        # Convert any bool values to int
                        if isinstance(cfgvalue, (bool)):
                            cfgvalue=int(cfgvalue)

                        # Then only show numerics
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
                    if cfgkey[0]!="_":
                        if isinstance(cfgvalue, numbers.Number):
                            if (cfgkey!="eo_harger_state_id") and (cfgkey!="eo_charger_state"):
                                    status[cfgkey]=cfgvalue

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(status).encode('utf-8'))
                return

            ##################################
            # This is a potential DoS end point.  Not sure how to secure this if we want
            # to offer the users an option.
            if self.path == "/restart":
                _LOGGER.info("User requested to restart openeo")
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "requested"}).encode("utf-8"))
                time.sleep(1.0) # Give time for the packet to be absorbed
                util.restart_python()
                
            ###################################################################
            ## expose the configuration the running config to the api
            ## we can also use POST/setconfig to write the configuration
            if self.path == "/getconfig":
                self.load_config()
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(self.config).encode("utf-8"))
                return
            ###################################################################
            ## expose the logger module metrics to the api, if that is available
            ## in cfg
            if re.search("^/debugdata",self.path):
                results = {"configDB":str(globalState.configDB)}
                for cmd in ["whoami",
                            "df -k",
                            "netstat -4l",
                            "ps -ef | grep openeo",
                            "free -h",
                            "systemctl status openeo --no-pager  --output=short-precise",
                            "ls -l /home/pi/releases/"]:
                    try:
                        result = subprocess.run(
                            cmd,
                            shell=True,           # allows string commands
                            capture_output=True,  # capture stdout/stderr
                            text=True,            # decode to string
                            check=True            # raise exception if exit code != 0
                        )
                        results[cmd] = result.stdout.strip()
                    except subprocess.CalledProcessError as e:
                        results[cmd] = f"Error: {e.stderr.strip() or e}"
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(results).encode("utf-8"))
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
                    query_series = query_components.get('series', [''])[0]  # Default to None if not found

                    try:
                        query_since = datetime.datetime.strptime(query_since,"%Y-%m-%d %H:%M:%S.%f")
                    except ValueError:
                        query_since=None

                    try:
                        query_series = query_series.split(",")
                    except ValueError:
                        query_series=None
                    if query_series==['']:
                        query_series=None

                    self.send_response(200)
                    self.send_header("Content-type", "application/json")
                    self.end_headers()

                    if (query_type=="plotly"):

                            self.wfile.write(json.dumps(globalState.stateDict["_dataLog"].get_plotly(query_since,query_series),default=str).encode("utf-8"))
                            return
                    else:
                            self.wfile.write(json.dumps(globalState.stateDict["_dataLog"].get_data(query_since,query_series),default=str).encode("utf-8"))
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
            
            # Try to prevent directory backtracking.  If we detect ".." in the URL, that's not allowed.
            if ".." in self.path:
                self.send_error(403, "Forbidden - but, nice try")
                return
            
            path_components = urllib.parse.urlsplit(self.path)
            _LOGGER.info("Path components: %s" % repr(path_components))
            
            # Handle root request
            req_path = path_components.path
            if req_path == "/" or req_path == "":
                req_path = "/home.html"
            
            file_path  = 'lib/configserver' + req_path
            _LOGGER.debug("serving: " + file_path)
                
            file, ext = os.path.splitext(file_path)
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
                        with open(file_path, mode) as f:
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

                # write configuration update to sqlite
                globalState.configDB.setDict(post_data,False)

                # Now instruct all modules to reconfigure themselves. Probably overkill
                newconfig={}
                for modulename,module in globalState.stateDict["_moduleDict"].copy().items():
                    module.configure(globalState.configDB.get(modulename))
                    newconfig[modulename]=module.pluginConfig

                # reload local config from modules
                # note there is a chance/probability that the modules may not have seen the configuration
                # update yet, as configure() will only be run on the next main loop iteration after the 
                # setDict() has completed, so we probably don't want to *depend* on that.
                #self.load_config()
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success", "config": newconfig}).encode("utf-8"))
                _LOGGER.info('Config saved')
                return

            elif self.path == "/setsettings":
                ##################################
                # API for syncing settings via POST variables.
                # This is effectively the same as /setconfig, but does not require the data to be serialised
                # as JSON, accepting colon-delimited variables to build the mergable dictionary.
                # It redirects the user to the settings.html page when done.
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length).decode('utf-8')
                post_vars = urllib.parse.parse_qsl(post_data)
                
                # It is legal for POST keys to be duplicated; that shouldn't happen when saving settings, but #
                # even if it does, we'll just take the last value we see.

                modulelist=[]
                for modulekey, value in post_vars:
                    module,key=modulekey.split(':',1)
                    # keep a list of modules that we're touching
                    if module not in modulelist:
                        modulelist.append(module)
                    _LOGGER.debug("%r : %r : %r" % (module, key, value))
                    globalState.configDB.set(module,key,value)
                
                # Now instruct all modules to reconfigure themselves. Probably overkill
                newconfig={}
                for modulename,module in globalState.stateDict["_moduleDict"].copy().items():
                    module.configure(globalState.configDB.get(modulename))
                    newconfig[modulename]=module.pluginConfig

                self.set_context()
               
                self.send_response(303) # 303 See Other, used after POST request to indicate resubmission should not occur
                self.send_header('Location', '/settings.html?toast2success=1')
                self.end_headers()
            elif self.path == "/setmode":
                ##################################
                # API for changing the mode.  Depending upon the selected mode, one or more modules 
                # may be enabled or disabled at once.
                content_length = int(self.headers['Content-Length'])
                
                try:
                    post_data = json.loads(self.rfile.read(content_length).decode('utf-8'))
                    new_mode = str(post_data["newmode"]).lower().strip()
                    #self.load_config()
                    
                    _LOGGER.info("Set mode request: '%s'" % new_mode)
                
                    if new_mode == "schedule":
                        # Disable all modules except the reserved ones
                        #self.switch_modules(0)
                        # Enable the scheduler
                        globalState.configDB.set("scheduler","enabled",True)
                        globalState.configDB.set("switch","enabled",False)

                    elif new_mode == "manual":
                        # Disable all modules except the reserved ones
                        #self.switch_modules(0)
                        # Enable the switch module
                        globalState.configDB.set("scheduler","enabled",False)
                        globalState.configDB.set("switch","enabled",True)

                    elif new_mode == "remote":
                        # Disable the switch & schedule module
                        globalState.configDB.set("scheduler","enabled",False)
                        globalState.configDB.set("switch","enabled",False)

                        # Enable all modules, don't touch the reserved ones.
                        #self.switch_modules(1)
                    else:
                        raise RuntimeError("unsupported mode %s" % new_mode)
                        
                    
                    # Sync to disk.  This is required to keep the scheduler up to date,
                    # which is probably a limitation that should be fixed eventually.
                    # write configuration update to sqlite
                    globalState.configDB.set("chargeroptions","mode",new_mode)
                    
                    # Now instruct all modules to reconfigure themselves. Probably overkill
                    newconfig={}
                    for modulename,module in globalState.stateDict["_moduleDict"].copy().items():
                        module.configure(globalState.configDB.get(modulename))
                        newconfig[modulename]=module.pluginConfig

                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "success", "config": newconfig}).encode("utf-8"))
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
