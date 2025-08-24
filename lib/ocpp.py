"""
OpenEO Module: OCPP Integration
This module acts as a way to remotely control an openeo instance from an OCPP 
central server.

Configuration example:
"ocpp": 
{"websocket" : "ws://homeassistant.local:9000/",
 "name" : "My OCPP Charger", "point_id" : "CP_1"}

Module will create a JSON cache file at 'ocpp_config.json'.

Author: T.Oldbury
MIT Licence
"""

import logging, time, threading, traceback, json
import asyncio, websockets
from datetime import datetime

from ocpp.routing import on
from ocpp.v16 import ChargePoint, call, call_result
from ocpp.v16.enums import *
from ocpp.v16.datatypes import *

import globalState, util

EVENT_START_CHARGING = 1
EVENT_STOP_CHARGING = 2

PLUGIN_VERSION = "0.0.3"

# logging for use in this module
_LOGGER = logging.getLogger(__name__)

def strip_start(string):
    """Remove the suffix -start, if it is present."""
    if string.endswith("-start"):
        return string[:-6]
    else:
        return string

class ChargerService(ChargePoint):
    """Implements the ChargePoint service for OCPP.  Only one connector is supported, connector
    id #1, with overall charge point as id #0.
    
    This has to be a derived class of ChargePoint, but I didn't feel comfortable merging it 
    completely with the overall plugin service."""
    connected = False
    charger_state = "start"
    last_ocpp_state = ChargePointStatus.unavailable
    ocpp_state = ChargePointStatus.unavailable
    name = "unnamed"
    vendor = "openeo"
    available = False
    transaction_id_tag = ""
    heartbeat_interval = 60
    service_event_queue = []
    
    # This is the default configuration if a JSON set is not available.
    ocpp_config = {
        "GetConfigurationMaxKeys" : 50,
        "AuthorizeRemoteTxRequests" : False,
        "ClockAlignedDataInterval" : 0,
        "ConnectionTimedOut" : 60,
        "ConnectorPhaseRotation" : "NotApplicable", # Single phase charger, no phase rotation
        "LocalAuthorizeOffline" : False,
        "LocalPreAuthorize" : False,
        "MeterValuesAlignedData" : "",
        "MeterValuesAlignedDataMaxLength" : "",
        "MeterValuesSampledData" : "",
        "MeterValuesSampledInterval" : 1,           # Data available once per second
        "ResetRetries" : 5,
        "StopTransactionOnEVSideDisconnect" : True, # We shall stop the transaction early when the EV disconnects @TODO
        "StopTransactionOnInvalidId" : False,       # We do not support authentication, so this has no meaning
        "StopTxnAlignedData" : "",                  # I genuinely have no idea, but it's required
        "StopTxnSampledData" : "",                  # ^^^
        "SupportedFeatureProfiles" : "Core,Reservation",
        "TransactionMessageAttempts" : 3,           # @FIXME I don't think we will be respecting this for now
        "TransactionMessageRetryInterval" : 5,      # @FIXME ^^^
        "UnlockConnectorOnEVSideDisconnect" : True, # True... but only because the EVSE doesn't have a lock (AFAIK)
        "NumberOfConnectors" : 1,
        "HeartbeatInterval" : 60,
        "MinimumStatusDuration" : 5
    }
    
    # If 'True' is set here, the parameter cannot be edited.
    ocpp_params_readonly = {
        "GetConfigurationMaxKeys" : True,
        "AuthorizeRemoteTxRequests" : True,
        "ClockAlignedDataInterval" : True,
        "ConnectionTimedOut" : True,
        "ConnectorPhaseRotation" : True, 
        "LocalAuthorizeOffline" : True,
        "LocalPreAuthorize" : True,
        "MeterValuesAlignedData" : False,
        "MeterValuesAlignedDataMaxLength" : False,
        "MeterValuesSampledData" : False,
        "MeterValuesSampledInterval" : False,
        "ResetRetries" : True,
        "StopTransactionOnEVSideDisconnect" : False, 
        "StopTransactionOnInvalidId" : False,
        "StopTxnAlignedData" : True,
        "StopTxnSampledData" : True,
        "SupportedFeatureProfiles" : True,
        "TransactionMessageAttempts" : True,
        "TransactionMessageRetryInterval" : True,
        "UnlockConnectorOnEVSideDisconnect" : True,
        "NumberOfConnectors" : True,
        "HeartbeatInterval" : False,
        "MinimumStatusDuration" : False
    }
    
    # Measured parameters that are supported, set from the EO data.
    measured_parameters = {
        "Current.Import" : 0,
        "Current.Offered" : 0,
        "Frequency" : 0,
        "Power.Active.Import" : 0,
        "Power.Offered" : 0,
        "Temperature" : 0,
        "Voltage" : 0
    }
    
    measured_parameters_valid = False
    
    async def send_heartbeat(self):
        _LOGGER.info("OCPP: send_heartbeat()")
        
        request = call.Heartbeat()
        await self.call(request)
    
    async def send_start_transaction(self, _id_tag):
        # Sent when a transaction starts.
        _LOGGER.info("OCPP: send_start_transaction(%s)" % _id_tag)
        
        request = call.StartTransaction(
            connector_id=1,
            id_tag=_id_tag,
            meter_start=0,
            timestamp=datetime.now().isoformat())
            
        response = await self.call(request)
        _LOGGER.info("OCPP: send_start_transaction(%s) response %r" % (_id_tag, response))
    
    async def send_stop_transaction(self, _id_tag):
        # Sent when a transaction stops.
        _LOGGER.info("OCPP: send_stop_transaction(%s)" % _id_tag)
        
        request = call.StopTransaction(
            transaction_id=0,
            id_tag=_id_tag,
            meter_stop=0,
            timestamp=datetime.now().isoformat())
            
        await self.call(request)
    
    async def send_status_notification(self):
        # Check the status of the charging system.
        state = ChargePointStatus.unavailable
        overall_state = ChargePointStatus.unavailable
        error = ChargePointErrorCode.no_error
        vendor_error = "No Error"
        
        # For the purposes of this logic, strip "-start" from the status if it is present.
        # (For the charging status, we use the intermediate state to handle starting a session.)
        charger_state = strip_start(self.charger_state)
        has_start = (charger_state != self.charger_state)
        
        if charger_state == "plug-present":
            _LOGGER.info("OCPP: charge point is preparing")
            state = ChargePointStatus.preparing
            overall_state = ChargePointStatus.unavailable
        elif charger_state == "car-connected":
            _LOGGER.info("OCPP: charge point is suspended-ev")
            state = ChargePointStatus.suspended_ev  # might be 'charging'
            overall_state = ChargePointStatus.unavailable
        elif charger_state == "charge-suspended":
            _LOGGER.info("OCPP: charge point is suspended-evse")
            state = ChargePointStatus.suspended_evse
            overall_state = ChargePointStatus.unavailable
        elif charger_state == "charging":
            if self.charger_amp_limit > 0:
                _LOGGER.info("OCPP: charge point is charging")
                state = ChargePointStatus.charging
                overall_state = ChargePointStatus.unavailable
            elif has_start:
                _LOGGER.info("OCPP: charge point is preparing to charge")
                state = ChargePointStatus.preparing
                overall_state = ChargePointStatus.unavailable
            else:
                _LOGGER.info("OCPP: charge point is charging but current limit set to zero - emulating Available")
                state = ChargePointStatus.available
                overall_state = ChargePointStatus.available
        elif charger_state == "mains-fault":
            _LOGGER.info("OCPP: charge point is faulted")
            state = ChargePointStatus.faulted
            error = ChargePointErrorCode.other_error
            overall_state = ChargePointStatus.unavailable
            vendor_error = "Mains Fault"
        elif charger_state == "idle" or charger_state == "start":
            _LOGGER.info("OCPP: charge point is available")
            state = ChargePointStatus.available
            overall_state = ChargePointStatus.available
        
        _LOGGER.info("OCPP: sent status notification to CS")
        self.last_ocpp_state = state
        await self.call(call.StatusNotification(connector_id=0, status=overall_state, error_code=error, vendor_error_code=vendor_error))
        await self.call(call.StatusNotification(connector_id=1, status=state, error_code=error, vendor_error_code=vendor_error))
    
    async def send_meter_values(self, meter_value_req=""):
        _LOGGER.info("OCPP: send_meter_values()")
        
        if not self.measured_parameters_valid:
            _LOGGER.warning("OCPP: meter data not yet valid, not sending")
            return
        
        if len(meter_value_req) > 0:
            desired = meter_value_req.split(',')
        else:
            desired = self.ocpp_config['MeterValuesSampledData'].split(',')
            
        measure_result = []
        now = datetime.now().isoformat()
        
        for measurand in desired:
            if measurand in self.measured_parameters:
                measure_result.append(MeterValue(now, \
                    [{'context' : 'Sample.Periodic', 
                      'format' : 'SignedData', 
                      'measurand' : measurand, 
                      'value' : str(self.measured_parameters[measurand])}]))
        
        if len(measure_result) > 0:
            request = call.MeterValues(connector_id=0, meter_value=measure_result)
            await self.call(request)
        else:
            _LOGGER.warning("OCPP: send_meter_values() -> no measurands yet, not sending")
    
    async def send_boot_notification(self):
        _LOGGER.info("OCPP: send_boot_notification()")
        
        request = call.BootNotification(
            charge_point_model=str(self.name),
            charge_point_vendor=str(self.vendor),
            charge_box_serial_number="0000000",   # @TODO
            charge_point_serial_number="0000000", # @TODO
            firmware_version=str(PLUGIN_VERSION)
        )
        response: call_result.BootNotification = await self.call(request)

        if response.status == RegistrationStatus.accepted:
            _LOGGER.debug("OCPP: Connected to central server")
            _LOGGER.debug("OCPP: Server requests a heartbeat every %d seconds" % response.interval)
            self.heartbeat_interval = response.interval
            self.ocpp_config["HeartbeatInterval"] = response.interval
            self.connected = True
        else:
            _LOGGER.warn("OCPP: Connection was refused")
    
    def set_charger_state(self, new_state, cur_limit):
        _LOGGER.info("OCPP: set_charger_state(%s,%d)" % (new_state, cur_limit))
        self.charger_state = new_state
        self.charger_amp_limit = cur_limit
    
    def load_ocpp_config_json(self):
        """On startup, load the configuration from JSON, if it exists."""
        try:
            f = open("ocpp_config.json", "r")
            config = json.loads(f.read())
            f.close()
            self.ocpp_config = config
            self._old_ocpp_config = config
        except Exception as e:
            _LOGGER.warning("OCPP: json config data couldn't be loaded: %r" % e)
    
    def save_ocpp_config_json(self):
        """If the OCPP state changes, we need to save the config to JSON so it can
        survive a reboot.  Some CentralSystems (like HASS) only update this when 
        first adding a charger."""
        _LOGGER.info("OCPP: syncing OCPP configuration to disk as change has occurred")
        json_data = json.dumps(self.ocpp_config, indent=4)
        f = open("ocpp_config.json", "w")
        f.write(json_data)
        f.close()
    
    @on(Action.remote_start_transaction)
    async def on_remote_start_transaction(self, **kwargs):
        """A 'RemoteStartTransaction' is used to request a charging session begin.  We set
        our charging current request to the value defined by the charging profile, or the 
        maximum possible if that has not syet been defined.  Note that local charging current
        requests or limits can override this."""
        # We always accept the transaction.
        _LOGGER.info("OCPP: remote_start_transaction(%s)" % repr(kwargs))
        self.service_event_queue.append(EVENT_START_CHARGING)
        
        return call_result.RemoteStartTransaction(status=RemoteStartStopStatus.accepted)
    
    @on(Action.remote_stop_transaction)
    async def on_remote_stop_transaction(self, **kwargs):
        """A 'RemoteStopTransaction' is used to request a charging session stops."""
        # We always accept the transaction.
        _LOGGER.info("OCPP: remote_stop_transaction(%s)" % repr(kwargs))
        self.service_event_queue.append(EVENT_STOP_CHARGING)
        
        return call_result.RemoteStopTransaction(status=RemoteStartStopStatus.accepted)
        
    @on(Action.get_configuration)
    async def on_get_configuration(self, **kwargs):
        """A 'GetConfiguration' is used by the server to request some configuration data
        from the EVSE.  This is answered via the ocpp_config dictionary and, ultimately,
        a GetConfiguration.conf response."""
        # We always accept the transaction.
        _LOGGER.info("OCPP: get_configuration(%s)" % repr(kwargs))
        response = []
        unknown_key = []
        
        for key in kwargs['key']:
            if key in self.ocpp_config:
                response.append({'key' : key, 'value' : str(self.ocpp_config[key]), 'readonly' : False })
            else:
                unknown_key.append(key)
        
        for key in unknown_key:
            _LOGGER.warning("OCPP: Unknown configuration key: %s" % key)
        
        return call_result.GetConfiguration(
            configuration_key=response,
            unknown_key=unknown_key
        )
        
    @on(Action.change_configuration)
    async def on_change_configuration(self, **kwargs):
        """A 'ChangeConfiguration' is used by the server to set some configuration data
        on the EVSE.  This is responded to with a ChangeConfiguration.conf response."""
        # We always accept the transaction.
        _LOGGER.info("OCPP: change_configuration(%s)" % repr(kwargs))
        
        try:
            key, val = kwargs['key'], kwargs['value']
            type_of = type(self.ocpp_config[key])
            
            # If a parameter doesn't exist, reject the change.
            if key not in self.ocpp_config:
                _LOGGER.warning("OCPP: attempt to write unknown key %s")          
                return call_result.ChangeConfiguration(
                    status=ConfigurationStatus.not_supported
                )
            else:
                # If a parameter is read only, reject the change
                if self.ocpp_params_readonly[key]:    
                    _LOGGER.warning("OCPP: attempt to write read only key %s")
                    return call_result.ChangeConfiguration(
                        status=ConfigurationStatus.not_supported
                    )
                else:
                    change = False
                    
                    # Handle special case of MeterValuesSampledData or MeterValuesAlignedData
                    if key == "MeterValuesSampledData" or key == "MeterValuesAlignedData":
                        # If measureand isn't supported by us, reject the configuration change.
                        # (But only if there is exactly one measurand in the list).
                        if "," not in str(val):
                            if str(val) not in self.measured_parameters.keys():
                                _LOGGER.info("OCPP: rejecting unsupported measurand '%s'" % str(val))
                                return call_result.ChangeConfiguration(
                                    status=ConfigurationStatus.rejected
                                )
                    
                    # Type punning.  The existing type is used to cast to the new type.
                    if type_of is int:
                        if self.ocpp_config[key] != int(val):
                            self.ocpp_config[key] = int(val)
                            change = True
                    else:
                        if self.ocpp_config[key] != str(val):
                            self.ocpp_config[key] = str(val)
                            change = True
                    
                    if change:
                        self.save_ocpp_config_json()
                    
                    return call_result.ChangeConfiguration(
                        status=ConfigurationStatus.accepted
                    )
        except Exception as e:
            _LOGGER.info("OCPP: exception trying to convert type or save key: %r" % e)
            return call_result.ChangeConfiguration(
                status=ConfigurationStatus.rejected
            )
        
    @on(Action.change_availability)
    async def on_change_availability(self, **kwargs):
        """An 'ack' to the change availability message.  We always accept the request."""
        _LOGGER.info("OCPP: Got request to change_availability(%s)" % repr(kwargs))
        
        if kwargs['type'] == 'Operative':
            _LOGGER.info("OCPP: Becoming available by request of CentralServer")
            self.availability = True
        else:
            _LOGGER.info("OCPP: Going unavailable by request of CentralServer")
            self.availability = False
        
        return call_result.ChangeAvailability(
            status=AvailabilityStatus.accepted
        )
        
    @on(Action.unlock_connector)
    async def on_unlock_connector(self, **kwargs):
        """We do not support connector unlock."""
        _LOGGER.info("OCPP: Got request to unlock_connector(%s) -> NotSupported" % repr(kwargs))
        
        return call_result.UnlockConnector(
            status=UnlockStatus.not_supported
        )
        
    @on(Action.reset)
    async def on_reset(self, **kwargs):
        """We do not support reset requests yet.  In the future, this could trigger a reboot
        of the charger, perhaps."""
        _LOGGER.info("OCPP: Got request to reset(%s) -> Rejected" % repr(kwargs))
        
        return call_result.Reset(
            status=ResetStatus.rejected
        )
    
class ocppClassPlugin:
    PRETTY_NAME = "OCPP"
    CORE_PLUGIN = False
    myName = "ocpp"

    config = {}
    thread = None
    connected = False
    last_heartbeat = 0
    last_status = 0
    last_meter_data = 0
    last_temperature = 0
    req_heartbeat = False
    service = None
    charger_state = ""
    last_charger_state = ""
    charging_state = False
    charging_current = 32
    charger_amps_limit = 32
    skip = False
    new_status = True
    has_sync = False
    
    event_queue = []
    
    # These should never change after we initialise
    websocket_uri = ""
    point_id = ""
    name = ""
    protos = None
    
    def __str__(self):
        return self.myName

    def configure(self, configParam):
        _LOGGER.debug("OCPP: reconfiguring")
        self.config = configParam
        self.sync_state(self.config)
        
        try:
            self.websocket_uri = str(self.config["websocket"]).strip()
            _LOGGER.debug("OCPP: websocket: %s" % self.websocket_uri)
        except KeyError:
            _LOGGER.warning("OCPP: websocket is not specified, aborting module init.")
            return
        
        if not self.websocket_uri.startswith("ws://") or not self.websocket_uri.endswith("/") or self.websocket_uri.count("/") > 3:
            _LOGGER.warning("OCPP: websocket ID is not well-formed and might not work, it needs to look like: ws://ip-or-dns-name:1234/; do not include the CP ID.")
        
        # OCPP1.6 or OCPP2.0.1 are implemented.  We prefer 2.0.1, then fall back to 1.6.
        self.protos = ["occp2.0.1", "ocpp1.6"]
        
        if "charger_id" not in globalState.stateDict:
            self.point_id = "ChargePoint1"
        else:
            self.point_id = str(globalState.stateDict["charger_id"])
            
        if "charger_name" not in globalState.stateDict:
            self.name = "Unnamed openeo Charger"
        else:
            self.name = str(globalState.stateDict["charger_name"])

    def get_config(self):
        return self.config
        
    def sync_state(self, configParam):
        _LOGGER.debug("OCPP: sync state")
        
        # Skip an update, if we have just made a change, as it might not have propagated
        # just yet.
        if self.skip:
            _LOGGER.info("OCPP: skipping update")
            self.skip = False
            return
            
        if "eo_amps_limit" in configParam:
            self.charger_amps_limit = configParam["eo_amps_limit"]
        
        if "eo_charger_state" in configParam and self.service:
            self.service.set_charger_state(configParam["eo_charger_state"], self.charger_amps_limit)
            self.charger_state = configParam["eo_charger_state"]
        else:
            _LOGGER.warning("OCPP: no charger state yet or service not init")
        
        if self.service:
            try:
                self.service.measured_parameters["Voltage"] = configParam["eo_live_voltage"]
                self.service.measured_parameters["Current.Import"] = configParam["eo_current_vehicle"]
                self.service.measured_parameters["Current.Offered"] = self.charger_amps_limit
                self.service.measured_parameters["Frequency"] = configParam["eo_mains_frequency"]
                self.service.measured_parameters["Power.Active.Import"] = configParam["eo_power_delivered"]
                self.service.measured_parameters["Power.Offered"] = configParam["eo_live_voltage"] * self.charger_amps_limit * 1e-3
                self.service.measured_parameters["Temperature"] = configParam["cpu_temperature"]
                self.service.measured_parameters_valid = True
            except KeyError as e:
                _LOGGER.warning("OCPP: incomplete measurement data, not syncing yet (%r)" % e)
        
        if len(self.charger_state) > 0:
            charger_state = strip_start(self.charger_state)
            # Handle 0A: this is not charging
            if charger_state == "charging" and self.last_charger_state != "charging" and (self.charger_amps_limit > 0):
                self.event_queue.append(EVENT_START_CHARGING)
                self.last_charger_state = charger_state
            if self.last_charger_state == "charging" and self.last_charger_state != "charging":
                self.event_queue.append(EVENT_STOP_CHARGING)
                self.last_charger_state = charger_state
        
        self.has_sync = True
    
    def poll(self):
        # Output is the configured charging current if we are charging, and zero if not
        _LOGGER.info("OCPP: charging state: %d, %d" % (self.charging_state, self.charging_current))
        self.has_poll = True
        if self.charging_state:
            return self.charging_current
        else:
            return 0

    def __init__(self, configParam):
        _LOGGER.debug("Initialising Module: OCPP")
        self.configure(configParam)
        
        # Start the OCPP sub-thread
        _LOGGER.debug("Starting OCPP thread")
        self.thread = threading.Thread(target=self.ocpp_service)
        self.thread.start()
    
    async def process_event(self, ev):
        if ev == EVENT_START_CHARGING:
            self.service.set_charger_state("charging-start", self.charger_amps_limit)
            await self.service.send_start_transaction("<unknown>")
            await self.service.send_status_notification()
            self.charging_state = True
            self.new_status = True
            self.has_sync = False
            self.skip = True
        if ev == EVENT_STOP_CHARGING:
            self.service.set_charger_state("charge-suspended", self.charger_amps_limit)
            await self.service.send_stop_transaction("<unknown>")
            await self.service.send_status_notification()
            self.charging_state = False
            self.new_status = True
            self.has_sync = False
            self.skip = True
    
    async def event_loop(self):
        n = 0
        while True:
            if n % 10 == 0:
                _LOGGER.debug("OCPP: event loop tick %d" % n)
                
            await asyncio.sleep(0.5)
            
            # When events happen, handle them in a FIFO manner.
            while len(self.event_queue) > 0:
                ev = self.event_queue.pop()
                _LOGGER.info("processing local event: %r" % ev)
                await self.process_event(ev)
            while len(self.service.service_event_queue) > 0:
                ev = self.service.service_event_queue.pop()
                _LOGGER.info("processing service event: %r" % ev)
                await self.process_event(ev)
               
            # Every @interval seconds, send a Heartbeat message.
            if (time.time() - self.last_heartbeat) >= int(self.service.ocpp_config['HeartbeatInterval']):
                _LOGGER.debug("OCPP: generate heartbeat request")
                await self.service.send_heartbeat()
                self.last_heartbeat = time.time()
            
            # Every state change, send a Status message, but wait for a sync_state to have occurred.
            if self.new_status and self.has_sync:
                _LOGGER.info("OCPP: generate status request (new status), last message was %d seconds ago" % (time.time() - self.last_status))
                await self.service.send_status_notification()
                self.last_status = time.time()
                self.new_status = False
                self.has_sync = False
            
            # Every @interval seconds, send metering info.
            if (time.time() - self.last_meter_data) >= int(self.service.ocpp_config['MeterValuesSampledInterval']):
                await self.service.send_meter_values()
                self.last_meter_data = time.time()
            
            n += 1
    
    async def ocpp_service_main(self):
        while True:
            _LOGGER.info("OCPP: preparing to connect to OCPP server at %s using protocols %r" % (self.websocket_uri, self.protos))
            try:
                async with websockets.connect(
                    "%s%s" % (self.websocket_uri, self.point_id), subprotocols=self.protos
                ) as ws:
                    logger_ocpp = _LOGGER.getChild('ocpp-core')
                    logger_ocpp.setLevel(logging.WARNING)
                    self.service = ChargerService(self.point_id, ws, logger=logger_ocpp)
                    self.service.load_ocpp_config_json()
                    self.service.name = self.name
                    self.service_ready = True
                    
                    loop = asyncio.get_event_loop()

                    res = await asyncio.gather(
                        self.service.start(),
                        self.service.send_boot_notification(),
                        self.service.send_heartbeat(),
                        self.service.send_status_notification(),
                        self.event_loop()
                    )
            except websockets.exceptions.NegotiationError as e:
                _LOGGER.warning("OCPP: the server does not support our minimum OCCP version, it needs to be updated (%r)" % (self.websocket_uri, e))
            except (websockets.exceptions.InvalidStatusCode, ConnectionRefusedError, asyncio.exceptions.CancelledError, TimeoutError, OSError) as e:
                _LOGGER.warning("OCPP: unable to connect to the server at %s... retry in 10s (%r)" % (self.websocket_uri, e))
            except (websockets.exceptions.ConnectionClosedOK) as e:
                _LOGGER.warning("OCPP: server %s closed the connection.  Most likely, it is not ready for us yet (device not associated yet?) Retry in 10s..." % self.websocket_uri)
            except Exception as e:
                _LOGGER.warning("OCPP: some other fatal exception trying to connect to %s, aborting: %r" % (self.websocket_uri, e))
                _LOGGER.error(traceback.format_exc())
                break
                
            await asyncio.sleep(10)
            
    def ocpp_service(self):
        """A very simple wrapper for asyncio as this is a blocking call."""
        # Wait for the service to become ready.
        asyncio.run(self.ocpp_service_main())
        
    def get_user_settings(self):
        """Called from the set_context method to update user settings."""
        settings = []
        util.add_simple_setting(self.config, settings, 'url', "ocpp", ("websocket",), 'Central Server Websocket',
            note='This should not include the charge point ID.  It may include a port number.  Example: ws://homeassistant.local:9000/.', \
            default="", pattern='ws(s?):\/\/.*')
        return settings
        