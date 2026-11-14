#!/usr/bin/env python3
"""Run repaired audit contracts, saving new observations; never invokes a live host."""
import argparse
import json
from pathlib import Path
import platform
import sys
import unittest

KIT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(KIT/'tests'))

class Observed(unittest.TextTestResult):
    def __init__(self,*args,**kw):
        super().__init__(*args,**kw)
        self.observations=[]
    def addSuccess(self,test):
        super().addSuccess(test)
        self.observations.append({'test':test.id(),'passed':True})
    def addFailure(self,test,err):
        super().addFailure(test,err)
        self.observations.append({'test':test.id(),'passed':False,'detail':self._exc_info_to_string(err,test)})
    def addError(self,test,err):
        super().addError(test,err)
        self.observations.append({'test':test.id(),'passed':False,'detail':self._exc_info_to_string(err,test)})

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    suite=unittest.defaultTestLoader.discover(str(KIT/'tests'),pattern='test_repairs.py')
    result=unittest.TextTestRunner(verbosity=2,resultclass=Observed).run(suite)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps({'python':platform.python_version(),'platform':platform.platform(),
        'kind':'installed CLI, migrations, concurrent operations and repaired audits; fixture hooks; no live host',
        'total':result.testsRun,'passed':result.wasSuccessful(),'observations':result.observations},indent=2)+'\n')
    return int(not result.wasSuccessful())

if __name__=='__main__': sys.exit(main())
