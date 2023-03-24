#!/usr/bin/env python
from setuptools import setup, find_packages

setup(
    name='swiggy_order_hooks',
    author='Rahul Sathanapalli',
    author_email='skvrahul@gmail.com',
    description='Library to allow Swiggy Restaurant Partners to write custom handlers hooking into Swiggy\'s order notifications',
    packages=['swiggy_order_hooks'] + ['swiggy_order_hooks.' + pkg for pkg in find_packages('swiggy_order_hooks')],
    version='0.0.1',
    license='MIT'
)