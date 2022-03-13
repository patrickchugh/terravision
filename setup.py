from setuptools import setup

setup(
    name='terravision',
    version='0.1',
    py_modules=['terravision'],
    install_requires=[
        'Click',
        'python-hcl2',
        'GitPython',
        'graphviz',
        'requests',
        'tqdm'
    ],
    entry_points='''
        [console_scripts]
        terravision=terravision:cli
    ''',
)
