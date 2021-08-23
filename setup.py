#!/usr/bin/env python

import setuptools

setuptools.setup(
    name = 'pynoon',
    version = '0.0.17',
    license = 'MIT',
    description = 'Python library for Noon Home',
    author = 'Alistair Galbraith',
    author_email = 'github@alistairs.net',
    url = 'http://github.com/jkporter/pynoon',
    include_package_data=True,
	packages=setuptools.find_packages(),
    install_requires=['requests', 'websocket-client'],
    classifiers = [
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.9',
        'Topic :: Home Automation',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ]

)