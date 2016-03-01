#! /usr/bin/python
# Copyright 2015 Kevin Lynch
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import collectd
import json
import urllib2
import base64
import numbers

PREFIX = "marathon"
MARATHON_HOST = "localhost"
MARATHON_PORT = 8080
MARATHON_USER = None
MARATHON_PASS = None
MARATHON_URL = ""
CLEAN_METRICS = True
VERBOSE_LOGGING = False


def configure_callback(conf):
    """Received configuration information"""
    global MARATHON_HOST, MARATHON_PORT, MARATHON_URL, VERBOSE_LOGGING
    global MARATHON_USER, MARATHON_PASS
    global CLEAN_METRICS
    for node in conf.children:
        if node.key == 'Host':
            MARATHON_HOST = node.values[0]
        elif node.key == 'Port':
            MARATHON_PORT = int(node.values[0])
        elif node.key == 'User':
            MARATHON_USER = node.values[0]
        elif node.key == 'Pass':
            MARATHON_PASS = node.values[0]
        elif node.key == 'CleanMetrics':
            CLEAN_METRICS = bool(node.values[0])
        elif node.key == 'Verbose':
            VERBOSE_LOGGING = bool(node.values[0])
        else:
            collectd.warning('marathon plugin: Unknown config key: %s.' % node.key)

    MARATHON_URL = "http://" + MARATHON_HOST + ":" + str(MARATHON_PORT) + "/metrics"

    log_verbose('Configured with host=%s, port=%s, url=%s' % (MARATHON_HOST, MARATHON_PORT, MARATHON_URL))


def read_callback():
    """Parse stats response from Marathon"""
    log_verbose('Read callback called')
    try:
        request = urllib2.Request(MARATHON_URL)
        if MARATHON_USER is not None:
	    base64string = base64.encodestring('%s:%s' % (MARATHON_USER, MARATHON_PASS)).replace('\n', '')
	    request.add_header("Authorization", "Basic %s" % base64string)
	metrics = json.load(urllib2.urlopen(request, timeout=10))

        for group in ['gauges', 'histograms', 'meters', 'timers', 'counters']:
            for name,values in metrics.get(group, {}).items():
                for metric, value in values.items():
                    if isinstance(value, numbers.Number):
                        dispatch_stat('gauge', '.'.join((name, metric)), value)
    except urllib2.URLError as e:
        collectd.error('marathon plugin: Error connecting to %s - %r' % (MARATHON_URL, e))


def dispatch_stat(type, name, value):
    """Read a key from info response data and dispatch a value"""
    if value is None:
        collectd.warning('marathon plugin: Value not found for %s' % name)
        return
    log_verbose('Sending value[%s]: %s=%s' % (type, name, value))

    val = collectd.Values(plugin='marathon')
    val.type = type
    if CLEAN_METRICS:
        name = name.replace('mesosphere.marathon.', '')
        name_parts = name.split('.')
        name_parts.reverse()
        name = ".".join(name_parts)
    val.type_instance = name
    val.values = [value]
    # https://github.com/collectd/collectd/issues/716
    val.meta = {'0': True}
    val.dispatch()


def log_verbose(msg):
    if not VERBOSE_LOGGING:
        return
    collectd.info('marathon plugin [verbose]: %s' % msg)

collectd.register_config(configure_callback)
collectd.register_read(read_callback)
