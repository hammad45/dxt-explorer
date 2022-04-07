"""
DXT Explorer.

DXT Explorer Copyright (c) 2021, The Regents of the University of
California, through Lawrence Berkeley National Laboratory (subject
to receipt of any required approvals from the U.S. Dept. of Energy).
All rights reserved.

If you have questions about your rights to use or distribute this software,
please contact Berkeley Lab's Intellectual Property Office at
IPO@lbl.gov.

NOTICE.  This Software was developed under funding from the U.S. Department
of Energy and the U.S. Government consequently retains certain rights.  As
such, the U.S. Government has been granted for itself and others acting on
its behalf a paid-up, nonexclusive, irrevocable, worldwide license in the
Software to reproduce, distribute copies to the public, prepare derivative
works, and perform publicly and display publicly, and to permit others to do
so.
"""

import os
import sys
import csv
import shlex
import argparse
import subprocess
import webbrowser
import logging
import logging.handlers
import pkg_resources

from distutils.spawn import find_executable
from alive_progress import alive_bar


class Explorer:

    def __init__(self, args):
        """Initialize the explorer."""
        self.args = args

        self.configure_log()
        self.has_dxt_parser()
        self.has_r_support()

    def configure_log(self):
        """Configure the logging system."""
        self.logger = logging.getLogger('DXT Explorer')

        if self.args.debug:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO)

        # Defines the format of the logger
        formatter = logging.Formatter(
            '%(asctime)s %(module)s - %(levelname)s - %(message)s'
        )

        console = logging.StreamHandler()

        console.setFormatter(formatter)

        self.logger.addHandler(console)

    def run(self):
        self.is_darshan_file(self.args.darshan)
        self.parse(self.args.darshan)

        if self.args.output:
            self.prefix = self.args.output
        else:
            self.prefix = os.getcwd()

        if self.args.list_files:
            self.list_files(self.args.darshan)

            exit()

        self.generate_plot(self.args.darshan)

        if self.args.transfer:
            self.generate_transfer_plot(self.args.darshan)

        if self.args.spatiality:
            self.generate_spatiality_plot(self.args.darshan)

    def get_directory(self):
        """Determine the install path to find the execution scripts."""
        try:
            root = __file__
            if os.path.islink(root):
                root = os.path.realpath(root)

            return os.path.dirname(os.path.abspath(root))
        except Exception:
            return None

    def is_darshan_file(self, file):
        """Check if the provided file exists and is a .darshan file."""
        if not os.path.exists(self.args.darshan):
            self.logger.error('{}: NOT FOUND'.format(file))

            exit(-1)

        if not self.args.darshan.endswith('.darshan'):
            self.logger.error('{} is not a .darshan file'.format(file))

            exit(-1)

    def has_dxt_parser(self):
        """Check if `darshan-dxt-parser` is on PATH."""
        if find_executable('darshan-dxt-parser') is not None:
            self.logger.debug('darshan-dxt-parser: FOUND')
        else:
            self.logger.error('darshan-dxt-parser: NOT FOUND')

            exit(-1)

    def has_r_support(self):
        """Check if `Rscript` is on PATH."""
        if find_executable('Rscript') is not None:
            self.logger.debug('Rscript: FOUND')
        else:
            self.logger.error('Rscript: NOT FOUND')

            exit(-1)

    def dxt(self, file):
        """Parse the Darshan file to generate the .dxt trace file."""
        if os.path.exists(file + '.dxt'):
            self.logger.debug('using existing parsed Darshan file')

            return

        command = 'darshan-dxt-parser {0}'.format(file)

        args = shlex.split(command)

        self.logger.debug('parsing {} file'.format(file))

        with open('{}.dxt'.format(file), 'w') as output:
            s = subprocess.run(args, stderr=subprocess.PIPE, stdout=output)

        assert(s.returncode == 0)

    def parse(self, file):
        """Parse the .darshan.dxt file to generate a CSV file."""
        self.dxt(file)

        if os.path.exists(file + '.dxt.csv'):
            self.logger.debug('using existing intermediate CSV file')

            return

        self.logger.debug('generating an intermediate CSV file')

        with open(file + '.dxt') as f:
            lines = f.readlines()
            file_id = None

            with open(file + '.dxt.csv', 'w', newline='') as csvfile:
                w = csv.writer(csvfile)

                w.writerow([
                    'file_id',
                    'api',
                    'rank',
                    'operation',
                    'segment',
                    'offset',
                    'size',
                    'start',
                    'end',
                    'ost'
                ])

                for line in lines:
                    if 'file_id' in line:
                        file_id = line.split(',')[1].split(':')[1].strip()

                    if 'X_POSIX' in line:
                        info = line.replace('[', '').replace(']', '').split()

                        api = info[0]
                        rank = info[1]
                        operation = info[2]
                        segment = info[3]
                        offset = info[4]
                        size = info[5]
                        start = info[6]
                        end = info[7]

                        if len(info) == 9:
                            ost = info[8]
                        else:
                            ost = None

                        w.writerow([
                            file_id,
                            api.replace('X_', ''),
                            rank,
                            operation,
                            segment,
                            offset,
                            size,
                            start,
                            end,
                            ost
                        ])

                    if 'X_MPIIO' in line:
                        info = line.split()

                        api = info[0]
                        rank = info[1]
                        operation = info[2]

                        # Newer Darshan DXT logs have segment for MPI-IO
                        if len(info) == 8:
                            segment = info[3]
                            offset = info[4]
                            size = info[5]
                            start = info[6]
                            end = info[7]
                        else:
                            segment = -1
                            offset = info[3]
                            size = info[4]
                            start = info[5]
                            end = info[6]

                        if len(info) == 9:
                            ost = info[8]
                        else:
                            ost = None

                        w.writerow([
                            file_id,
                            api.replace('X_', ''),
                            rank,
                            operation,
                            segment,
                            offset,
                            size,
                            start,
                            end,
                            ost
                        ])

    def list_files(self, file):
        files = {}

        with open(file + '.dxt') as f:
            lines = f.readlines()

            for line in lines:
                if 'file_id' in line:
                    file_id = line.split(',')[1].split(':')[1].strip()
                    file_name = line.split(',')[2].split(':')[1].strip()

                    if file_id not in files.keys():
                        files[file_id] = file_name

        for file_id, file_name in files.items():
            self.logger.info('FILE: {} (ID {})'.format(file_name, file_id))

        self.logger.info('{} I/O trace observation records from {} files'.format(len(lines), len(files)))

        return files

    def subset_dataset(self, file, file_ids):
        self.logger.info('generating datasets')

        with alive_bar(total=len(file_ids), title='', spinner=None, enrich_print=False) as bar:
            for file_id in file_ids:
                subset_dataset_file = '{}.{}'.format(file, file_id)

                if os.path.exists(subset_dataset_file + '.dxt.csv'):
                    self.logger.debug('using existing parsed Darshan file')

                    bar()
                    continue

                with open(file + '.dxt.csv') as f:
                    rows = csv.DictReader(f)

                    with open(subset_dataset_file + '.dxt.csv', 'w', newline='') as csvfile:
                        w = csv.writer(csvfile)

                        w.writerow([
                            'file_id',
                            'api',
                            'rank',
                            'operation',
                            'segment',
                            'offset',
                            'size',
                            'start',
                            'end',
                            'ost'
                        ])

                        for row in rows:
                            if file_id == row['file_id']:
                                w.writerow(row.values())

                bar()

    def generate_plot(self, file):
        """Generate an interactive operation plot."""
        limits = ''

        if self.args.start:
            limits += ' -s {} '.format(self.args.start)

        if self.args.end:
            limits += ' -e {} '.format(self.args.end)

        if self.args.start_rank:
            limits += ' -n {} '.format(self.args.start_rank)

        if self.args.end_rank:
            limits += ' -m {} '.format(self.args.end_rank)

        file_ids = self.list_files(file)

        # Generated the CSV files for each plot
        self.subset_dataset(file, file_ids)

        with alive_bar(total=len(file_ids), title='', spinner=None, enrich_print=False) as bar:
            for file_id, file_name in file_ids.items():
                output_file = '{}/{}.{}.operation.html'.format(self.prefix, file, file_id)

                path = 'plots/operation.R'
                script = pkg_resources.resource_filename(__name__, path)

                command = '{} -f {}.{}.dxt.csv {} -o {} -x {}'.format(
                    script,
                    file,
                    file_id,
                    limits,
                    output_file,
                    file_name
                )

                args = shlex.split(command)

                self.logger.info('generating interactive operation for: {}'.format(file_name))
                self.logger.debug(command)

                s = subprocess.run(args, stderr=subprocess.PIPE, stdout=subprocess.PIPE)

                if s.returncode == 0:
                    if os.path.exists(output_file):
                        self.logger.info('SUCCESS: {}'.format(output_file))
                    else:
                        self.logger.warning('no data to generate interactive plots')

                    if self.args.browser:
                        webbrowser.open('file://{}'.format(output_file), new=2)
                else:
                    self.logger.error('failed to generate the interactive plots (error %s)', s.returncode)

                    if s.stdout is not None:
                        for item in s.stdout.decode().split('\n'):
                            if item.strip() != '':
                                self.logger.debug(item)

                    if s.stderr is not None:
                        for item in s.stderr.decode().split('\n'):
                            if item.strip() != '':
                                self.logger.error(item)

                bar()

    def generate_transfer_plot(self, file):
        """Generate an interactive transfer plot."""
        limits = ''

        if self.args.start:
            limits += ' -s {} '.format(self.args.start)

        if self.args.end:
            limits += ' -e {} '.format(self.args.end)

        if self.args.start_rank:
            limits += ' -n {} '.format(self.args.start_rank)

        if self.args.end_rank:
            limits += ' -m {} '.format(self.args.end_rank)

        file_ids = self.list_files(file)

        # Generated the CSV files for each plot
        self.subset_dataset(file, file_ids)

        with alive_bar(total=len(file_ids), title='', spinner=None, enrich_print=False) as bar:
            for file_id, file_name in file_ids.items():
                output_file = '{}/{}.{}.transfer.html'.format(self.prefix, file, file_id)

                path = 'plots/transfer.R'
                script = pkg_resources.resource_filename(__name__, path)

                command = '{} -f {}.{}.dxt.csv -o {} -x {}'.format(
                    script,
                    file,
                    file_id,
                    output_file,
                    file_name
                )

                args = shlex.split(command)

                self.logger.info('generating interactive transfer for: {}'.format(file_name))
                self.logger.debug(command)

                s = subprocess.run(args, stderr=subprocess.PIPE, stdout=subprocess.PIPE)

                if s.returncode == 0:
                    self.logger.info('SUCCESS: {}'.format(output_file))

                    if self.args.browser:
                        webbrowser.open('file://{}.{}.transfer.html'.format(file, file_id), new=2)
                else:
                    self.logger.error('failed to generate the interactive plots (error %s)', s.returncode)

                    if s.stdout is not None:
                        for item in s.stdout.decode().split('\n'):
                            if item.strip() != '':
                                self.logger.debug(item)

                    if s.stderr is not None:
                        for item in s.stderr.decode().split('\n'):
                            if item.strip() != '':
                                self.logger.error(item)

                bar()

    def generate_spatiality_plot(self, file):
        """Generate an interactive spatiality plot."""
        file_ids = self.list_files(file)

        # Generated the CSV files for each plot
        self.subset_dataset(file, file_ids)

        with alive_bar(total=len(file_ids), title='', spinner=None, enrich_print=False) as bar:
            for file_id, file_name in file_ids.items():
                output_file = '{}/{}.{}.spatiality.html'.format(self.prefix, file, file_id)

                path = 'plots/spatiality.R'
                script = pkg_resources.resource_filename(__name__, path)

                command = '{} -f {}.{}.dxt.csv -o {} -x {}'.format(
                    script,
                    file,
                    file_id,
                    output_file,
                    file_name
                )

                args = shlex.split(command)

                self.logger.info('generating interactive spatiality for: {}'.format(file_name))
                self.logger.debug(command)

                s = subprocess.run(args, stderr=subprocess.PIPE, stdout=subprocess.PIPE)

                if s.returncode == 0:
                    if os.path.exists(output_file):
                        self.logger.info('SUCCESS: {}'.format(output_file))
                    else:
                        self.logger.warning('no data to generate spatiality plots')

                    if self.args.browser:
                        webbrowser.open('file://{}'.format(output_file), new=2)
                else:
                    self.logger.error('failed to generate the spatiality plots (error %s)', s.returncode)

                    if s.stdout is not None:
                        for item in s.stdout.decode().split('\n'):
                            if item.strip() != '':
                                self.logger.debug(item)

                    if s.stderr is not None:
                        for item in s.stderr.decode().split('\n'):
                            if item.strip() != '':
                                self.logger.error(item)

                bar()


def main():
    PARSER = argparse.ArgumentParser(
        description='DXT Explorer: '
    )

    PARSER.add_argument(
        'darshan',
        help='Input .darshan file'
    )

    PARSER.add_argument(
        '-o',
        '--output',
        default=sys.stdout,
        type=argparse.FileType('w'),
        help='Output directory'
    )

    PARSER.add_argument(
        '-t',
        '--transfer',
        default=False,
        action='store_true',
        help='Generate an interactive data transfer explorer'
    )

    PARSER.add_argument(
        '-s',
        '--spatiality',
        default=False,
        action='store_true',
        help='Generate an interactive spatiality explorer'
    )

    PARSER.add_argument(
        '-d',
        '--debug',
        action='store_true',
        dest='debug',
        help='Enable debug mode'
    )

    PARSER.add_argument(
        '-l',
        '--list',
        action='store_true',
        dest='list_files',
        help='List all the files with trace'
    )

    PARSER.add_argument(
        '--start',
        action='store',
        dest='start',
        help='Report starts from X seconds (e.g., 3.7) from beginning of the job'
    )

    PARSER.add_argument(
        '--end',
        action='store',
        dest='end',
        help='Report ends at X seconds (e.g., 3.9) from beginning of the job'
    )

    PARSER.add_argument(
        '--from',
        action='store',
        dest='start_rank',
        help='Report start from rank N'
    )

    PARSER.add_argument(
        '--to',
        action='store',
        dest='end_rank',
        help='Report up to rank M'
    )

    PARSER.add_argument(
        '--browser',
        default=False,
        action='store_true',
        dest='browser',
        help='Open the browser with the generated plot'
    )

    ARGS = PARSER.parse_args()

    EXPLORE = Explorer(ARGS)
    EXPLORE.run()


if __name__ == '__main__':
    main()
