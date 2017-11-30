#/usr/bin/env python
# -*- coding:utf-8 -*-
__author__ = 'qiaokaiqiang'

import boto3,os
from optparse import OptionParser
import threading,time,sys
try:
    import ConfigParser as ConfigParser
except ImportError as e:
    import configparser as ConfigParser
try:
    import queue as Queue
except ImportError as e:
    import Queue as Queue


q=Queue.Queue()
class confdict(object):
    def __init__(self):
        self.confpath = os.path.dirname(os.path.abspath(__file__)) + "/conf/conf2.ini"
        self.config = ConfigParser.ConfigParser()
        self.config.read(self.confpath)

    def getconfdict(self,confname):
        dconf = {}
        for i in self.config.options(confname):
            try:
                dconf[i] = self.config.get(confname, i)
            except KeyError as e:
                    print (e.message)
        return dconf


    def getregionconfdict(self):
         return self.getconfdict("region")

    def getinstancestatusconfdict(self):
        return self.getconfdict("instancestatus")

lock=threading.Lock()
class common(object):
    @staticmethod
    def connectbyregion(region):
        lock.acquire()
        client=boto3.client('ec2',region_name=region,)
        lock.release()
        return client

class getinstanceinfo(object):

    def __init__(self,status,regionname,regionnamedic):
        self.status=status
        self.regionname=regionname
        self.regionnamedic=regionnamedic


    def descinstance(self,y):
        hostlist=[]
        hostlistcomplex=[]
        clientbyregion=common().connectbyregion(self.regionname)
        if self.status!='all':
            instanceinfo=clientbyregion.describe_instances(
            Filters=[
                    {
                        'Name': 'instance-state-name',
                        'Values': [
                            self.status,
                        ]
                    },
                ],
            )
        else:
            instanceinfo=clientbyregion.describe_instances()
        for n in instanceinfo.get('Reservations'):
            for i in n['Instances']:
                 publicip=",".join([x.get('Association',{}).get('PublicIp','没有公网IP') for n in i['NetworkInterfaces'] for x in n['PrivateIpAddresses']])
                 privateip=",".join([x.get('PrivateIpAddress','没有私网IP')for n in i['NetworkInterfaces'] for x in n['PrivateIpAddresses']])
                 hostname="".join([  x.get('Value','没有主机名')   if x.get('Value','没有主机名') else "没有主机名" for x in i['Tags'] if x.get('Key') == "Name"  ])
                 hostname="".join([hostname if hostname else "没有主机名" ])
                 regionrealname=self.regionnamedic.get(i['Placement']['AvailabilityZone'][:-1])
                 a = [hostname, i['InstanceType'], i['Placement']['AvailabilityZone'], i['InstanceId'],privateip,publicip,i['State']['Name'], regionrealname]
                 q.put(a)

        if y=='y':
              while q.qsize()>0:
                   a=q.get()
                   print("  ".join(a))
              return
        elif y=='n':
              while q.qsize()>0:
                   a=q.get()
                   print("".join(a[0]))
              return
        else:
           return


    def descsingleinstance(self):
        pass



class operateinstance(object):
    def __init__(self,instancetagname):
        self.instancetagname=instancetagname
        self.getinstanceregionandid=self.getinstanceregionandid()
        self.regionname=self.getinstanceregionandid[0]
        self.insid=self.getinstanceregionandid[1]
        self.outerip=self.getinstanceregionandid[2]
        self.clientbyregion=common().connectbyregion(self.regionname)
        if self.insid is None:
            print("Not such host")


    def getinstanceregionandid(self):
        ifhostexsits=[]
        while q.qsize()>0:
            a=q.get()
            if self.instancetagname in a:
               ifhostexsits.append(self.instancetagname)
               return (str(a[2])[:-1],a[3],a[5])
            #else:
             #   exit("No Such Host")
        if len(ifhostexsits)==0:
            exit("No Such Host:[%s]"%(self.instancetagname))
    def stopinstance(self):
        response = self.clientbyregion.stop_instances(

            InstanceIds=[
                self.insid,
            ],
            #    DryRun=True
        )
        return response


    def startinstance(self):
        response=self.clientbyregion.start_instances(

            InstanceIds=[
                self.insid,
            ],
            #DryRun=True
        )
        return response
    def rebootinstance(self):
        response = self.clientbyregion.reboot_instances(

            InstanceIds=[
                self.insid,
            ],
            #DryRun=True
        )
        return response



if __name__ == '__main__':
    usage = "usage: %prog [options] arg1 arg2"
    optParser = OptionParser()
    optParser.add_option("-s", "--status", action="store", type="string", dest="status", default="all",
                         help="specify the instance status[pending | running | shutting-down | terminated | stopping | stopped]")
    optParser.add_option("-d", "--display", action="store", type="string", dest="display", default="-",
                         help="[yes|no]display the instance all info:{name,instance type,available region,instance id,public ip,instance running status}")
    optParser.add_option("", "--host", action="store", type="string", dest="host", default="",
                         help="Please input  EC2 host tag name")
    optParser.add_option("-a", "--action", action="store", type="string", dest="action", default="donothing",
                         help="Please input start or reboot or shutdown")
    options, args = optParser.parse_args()
    status = options.status
    display = options.display
    host=options.host
    action=options.action

    confdict=confdict()
    regionnamedic=confdict.getconfdict("region")
    instancestatusdic=confdict.getconfdict("instancestatus")
    actiondic=confdict.getconfdict("action")
    regionlist=[i for i in regionnamedic.keys()]
    thread_list=[]
    start_time=time.time()
    for region in regionlist:
        if status in instancestatusdic:
            descins = getinstanceinfo(status,region,regionnamedic).descinstance
            if display == 'yes' or display == 'y' or display == 'ye':
                t = threading.Thread(target=descins, args=("y",))
                thread_list.append(t)
                t.start()
            elif display == 'no' or display == 'n' or display == 'No':
                t = threading.Thread(target=descins, args=("n",))
                thread_list.append(t)
                t.start()
            elif display == "":
                exit("Must follow the argument,use -h for help")
            else:
                t = threading.Thread(target=descins, args=("-",))
                thread_list.append(t)
                t.start()

        else:
            exit("What you input after -s  is not correct!")
    for k in thread_list:
        k.join()

    if action  in actiondic:
        a=operateinstance(host)
        if action == 'start':
            b=a.startinstance()
            print("After START the OUTER IP is %s"%(a.outerip))
        elif action == 'shutdown':
            print("Before [%s] SHUTDOWN the OUTER IP is %s"%(host,a.outerip))
            b=a.stopinstance()
             
        elif action == 'reboot':
            b=a.rebootinstance()
            print("TIP:If an instance does not cleanly shut down within four minutes, Amazon EC2 performs a hard reboot")
        elif action == 'restart':
            beforeouterip=a.outerip
            print("Before [%s] SHUTDOWN the OUTER IP is %s"%(host,beforeouterip))
            Break_flag=False
            while not Break_flag:
                b=a.stopinstance()
                #print(b) only for debug
               # print(b)
                for n in b['StoppingInstances']:
                    #print type(n['CurrentState']['Name'])
                    if n['CurrentState']['Name'] == 'stopped':
                        # print("----")
                         while not Break_flag:
                            b=a.startinstance()
                            for i in b['StartingInstances']:
                                if i['CurrentState']['Name'] == "running":
                                     thread_list2=[]
                                     for region in regionlist:
                                        if status in instancestatusdic:
                                            descins = getinstanceinfo(status,region,regionnamedic).descinstance
                                            t = threading.Thread(target=descins, args=("-",))
                                            thread_list2.append(t)
                                            t.start()
                                     for m in thread_list2:
                                           m.join()
                                     afterouterip=operateinstance(host).outerip
                                     print("After [%s] RESTARTED the OUTER IP is %s"%(host,afterouterip))
                                     if beforeouterip != afterouterip:
                                         print ("The host %s outerip is changed to %s!"%(host,afterouterip))
                                     else:
                                         print("The host %s outerip is -NOT- changed!"%host)
                                     Break_flag=True
        print(b)
    elif action is 'donothing':
           pass
    else:
        print("You must input [start|stop|reboot],If an instance does not cleanly shut down within four minutes, Amazon EC2 performs a hard reboot.")


    print ("Cost %s"%(time.time()-start_time))
