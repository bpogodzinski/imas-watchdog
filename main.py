#! /usr/bin/env python
import argparse
import configparser
import glob
import logging
import os
import subprocess
import sys
from typing import List

from watchdog.events import FileSystemEventHandler, FileSystemEvent, EVENT_TYPE_CREATED, EVENT_TYPE_MODIFIED
from watchdog.observers.polling import PollingObserver


class EventHandler(FileSystemEventHandler):
    def __init__(self, action: str, arguments: List[str]):
        self.action = action
        self.arguments = arguments

    def handle(self, event: FileSystemEvent):
        if event.event_type in (EVENT_TYPE_CREATED, EVENT_TYPE_MODIFIED) and event.is_directory is False:
            logging.debug(event)
            logging.info(f'Running {action} {" ".join(arguments)} {event.src_path}')
            subprocess.run([action] + arguments + [path])

    def on_created(self, event):
        self.handle(event)

    def on_modified(self, event):
        self.handle(event)


def convert_to_arguments(additional: dict):
    for k, v in additional.items():
        yield '--{}'.format(k)
        yield v


if __name__ == '__main__':
    default_config = os.path.abspath(os.path.join(os.path.dirname(__file__), 'config.ini'))

    parser = argparse.ArgumentParser(description='Watch for creation of pulsefiles')
    parser.add_argument('--config', '-c', help=f'configuration file [default={default_config}]', default=default_config)
    parser.add_argument('--verbose', '-v', help=f'enable verbose output', action='store_true')
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    if not os.path.exists(args.config):
        logging.error(f'File does not exist: {args.config}')
        sys.exit()

    # parse config.ini file
    ini = configparser.ConfigParser()
    ini.read(args.config)

    required = {'glob', 'recursive', 'action', 'duration'}

    for section in ini.sections():
        missing = [name for name in required if name not in ini[section]]
        if missing:
            logging.warning(f'Ignoring section {section} in the config, because of missing required fields: {missing}')
            continue

        pattern = os.path.expanduser(os.path.expandvars(ini[section]['glob']))
        recursive = bool(ini[section]['recursive'])
        action = ini[section]['action']
        duration = float(ini[section]['duration'])

        # all ini section entries except the required ones are treated as command line arguments to event handler
        arguments = list(convert_to_arguments({key: ini[section][key] for key in ini[section].keys() - required}))

        # install watches
        event_handler = EventHandler(action, arguments)
        observer = PollingObserver(duration)
        for path in glob.iglob(pattern):
            observer.schedule(event_handler, path, recursive)
        observer.start()
        observer.join()
