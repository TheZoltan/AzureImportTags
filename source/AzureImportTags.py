# Commandline Parameters:
# azureimporttags.py [input_file] [migrated_from] [migrate_project] [azure_region] [subscriptiom] [client_id] [secret] [tenant]

import sys
import os
import json
from datetime import datetime
from azure.mgmt.resource import SubscriptionClient
import azure.common.credentials as creds
from azure.common.credentials import ServicePrincipalCredentials
from azure.common.client_factory import get_client_from_cli_profile
from azure.mgmt.resource import ResourceManagementClient
from azure.common.credentials import ServicePrincipalCredentials
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.compute.models import DiskCreateOption
from msrestazure.azure_exceptions import CloudError


# Main, start here
def main():

    print('Azure Import Tags Util v1.3')

    # Check that we have args
    if (len(sys.argv) < 10):
        print('YOU MUST SPECIFY THE CORRECT COMMAND LINE PARAMETERS:')
        print('Usage:')
        print('azureimporttags.py [vm_input_file] [input_file] [migrated_from] [migrate_project] [azure_region] [subscriptiom] [client_id] [secret] [tenant]')
        print('NOTE: the migrated_from field should contain one of these values:')
        print('  On Premise')
        print('  AWS')
        print('  Azure')
        print('  Equinix')
        print('  CGI')
        print('')
        sys.exit(1)


    # Get command line args
    if (sys.argv[0] == 'python'):
        vm_input_file = sys.argv[2]
        inputfile = sys.argv[3]
        migrated_from = sys.argv[4]
        migrate_project = sys.argv[5]
        region = sys.argv[6]
        sub_id = sys.argv[7]
        client_id = sys.argv[8]
        secret = sys.argv[9]
        tenant = sys.argv[10]
    else:
        vm_input_file = sys.argv[1]
        inputfile = sys.argv[2]
        migrated_from = sys.argv[3]
        migrate_project = sys.argv[4]
        region = sys.argv[5]
        sub_id = sys.argv[6]
        client_id = sys.argv[7]
        secret = sys.argv[8]
        tenant = sys.argv[9]


    print('VM List file:   ', vm_input_file)
    print('Inputfile:      ', inputfile)
    print('Region:         ', region)
    print('MigrateProject: ', migrate_project)
    print('sub_id:         ', sub_id)
    print('client_id:      ', client_id)
    print('secret:         ', secret)
    print('tenant:         ', tenant)


    # Start logging
    updatelog('------ Starting run ------')
    updatelog('Region: ', region)


    # If not a valid migrated_from field, abort with error
    migrated_from_cases = {
        'On Premise': 'On Premise',
        'AWS': 'AWS',
        'Azure': 'Azure',
        'Equinix': 'Equinix',
        'CGI': 'CGI',
        'Native': 'Native'
    }
    migrated_from = migrated_from_cases.get(migrated_from, 'INVALID')
    if (migrated_from == 'INVALID'):
        print('')
        print('ERROR: invalid migrated_from arg was passed')
        updatelog('ERROR: invalid migrated_from arg was passed: ', migrated_from)
        print('')
        exit(2)

    print('migrated_from: ', migrated_from)
    updatelog('migrated_from: ', migrated_from)

    # Get creds
    updatelog('Calling ServicePrincipalCredentials()')
    subscription_id = sub_id
    #credentials = ServicePrincipalCredentials(client_id = client_id, secret = secret, tenant = tenant)

    # Testing this code
    credentials = creds.get_azure_cli_credentials(resource=None, with_tenant=False)[0]
    sub_client = SubscriptionClient(credentials)


    # Create object for compute-related interactions
    updatelog('Calling ComputeManagementClient()')
    compute_client = ComputeManagementClient(credentials, subscription_id)


    # Read all tag data into taglist var
    taglist = []
    updatelog('Calling loadrecordsfromfile()')
    loadrecordsfromfile(inputfile, taglist)

    # Get VM input list file
    target_vm_list = get_target_vm_list(vm_input_file)

    # Get list of all Azure VMs and add to list
    #az_vm_list = []
    updatelog('Calling getallazvms()')
    #getallazvms(compute_client, az_vm_list, target_vm_list)
    az_vm_list = getallazvms(compute_client, target_vm_list)

    print('VMs: ', az_vm_list)

    # Tag'em
    updatelog('Calling tageachvm()')
    tageachvmfromlist(credentials, subscription_id, compute_client, migrated_from, migrate_project, region, taglist, az_vm_list)

    updatelog('------ Exiting ------')


# Write to log
def updatelog(*argv):

    # Get current date/time
    curdt = datetime.now()
    curdt_str = curdt.strftime('[%d-%b-%Y %H:%M:%S.%f] ')

    # Update log
    log_line = ''
    logfile = open('azureimporttags.log', 'a+')
    logfile.writelines(curdt_str)
    for arg in argv:
        logfile.writelines(arg)

    logfile.writelines('\n')
    logfile.close()


# Get list of target VMs
def get_target_vm_list(vm_input_file):

    with open(vm_input_file) as f:
        target_vm_list = [line.rstrip() for line in f]

    return target_vm_list


# If success, write to success file, if error, then write to error file
def writetosuccessfaillog(VMName, status):

    if (status == 'SUCCEEDED'):
        log = open('succeeded.log', 'a+')

    else:
        log = open('failed.log', 'a+')

    # Update file
    log.writelines(VMName)
    log.writelines('\n')

    # Close file
    log.close()


# Writes the tags to the specified VM
def tagyoureit(credentials, subscription_id, compute_client, migrated_from, migrate_project, region, VMName, resourcegroup, tagline):

    print('\nTag Virtual Machine: ', VMName)

    updatelog('(tagyoureit) tagging VM: ', VMName)

    # Build dict to use to populate the function call param
    tagdict = {}
    for tagitem in tagline:
        dictkey = tagitem['Key']
        dictval = tagitem['Value']
        tagdict[dictkey] = dictval

    # Add migrated_from value to dict
    tagdict['Migrated From'] = migrated_from

    # Add a migrateproject value to list
    tagdict['MigrateProject'] = migrate_project

    #print('tagdict: ', tagdict)

    #print('(tagging Item: ', tagline)

    # Obtain authentication to execute api functions
    updatelog('Calling ResourceManagementClient() in tagyourit()')
    resource_client = ResourceManagementClient(credentials, subscription_id)

    print('Tagging item Item: ', tagline)
    updatelog('Tag: ', json.dumps(tagline))
    updatelog('Calling compute_client.virtual_machines.create_or_update() in tagyourit()')
    async_vm_update = compute_client.virtual_machines.create_or_update(
        resourcegroup,
        VMName,
        {
            'location': region,
            'tags':
                tagdict
        }
    )
    async_vm_update.wait()

    print('VM ', VMName, ' was updated')
    writetosuccessfaillog(VMName, 'SUCCEEDED')

    updatelog('Tags for VM ', VMName, ' were updated')


# Tag each vm that is in the az_vm_list
def tageachvmfromlist(credentials, subscription_id, compute_client, migrated_from, migrate_project, region, taglist, az_vm_list):

    # Check params
    if (region == ''):
        updatelog('ERROR: in tageachvm() NULL region')

    print('----- in tageachvmfromlist() -----')

    # Search taglist for name= attribute that matches each az_vm_list element
    for vm_name in az_vm_list:
        print('Searching for ', vm_name, '...')

        for tagline in taglist:

            counter = 0
            #for taglistitem in taglist[counter]:
            for taglistitem in tagline:
                #print('Item: ', taglistitem)

                dictkey = taglistitem['Key']
                if (dictkey == 'Name'):
                    list_name = taglistitem['Value']
                    #print('Compare: ', list_name.upper(), ' List:', vm_name.upper())

                    if (list_name.upper() == vm_name.upper()):
                        print('Found record: ', vm_name)
                        print('Tags: ', taglist[counter])

                        # Do the work...
                        # Validate that this is a valid VM name and get the VM's resource group
                        resourcegroup = validatetagvms(compute_client, taglist, az_vm_list, vm_name)

                        # If no resource group found, then that's a problem. we need to fail this record
                        if (resourcegroup != ''):

                            print('Resource group (tageachvm): ', resourcegroup)
                            if (resourcegroup == ''):
                                updatelog('ERROR: empty resource group name in tageachvm()')

                            updatelog('Resource group for ', list_name, ' is ', resourcegroup)

                            # Tag this VM with this record
                            tagyoureit(credentials, subscription_id, compute_client, migrated_from, migrate_project,
                                       region, vm_name, resourcegroup, tagline)

                        else:
                            print('Error: no resource group was found for this VM:', vm_name)
                            updatelog('ERROR: no resource group was found for this VM! (', vm_name, ')')
                            writetosuccessfaillog(vm_name, 'FAILED')


                counter += 1


# List each tag for this VM
def tageachvm(credentials, subscription_id, compute_client, migrated_from, migrate_project, region, taglist, az_vm_list):

    # Check params
    if (region == ''):
        updatelog('ERROR: in tageachvm() NULL region')


    counter = 0
    for tagline in taglist:
        print('-----------------------------------')
        #print('TagLine: (size: ', len(taglist), ')', tagline)


        #itemcount = len(taglist[0])
        #print('Item Count in tageachvm ', itemcount)
        for item in taglist[counter]:
            print('Item: ', item)

            # If this is the 'name' tag, then grab it, we need it to identify the VM we're gonna tag
            dictkey = item['Key']
            if dictkey == 'Name':
                VMName = item['Value']
                print('VM Name: ', VMName)

                # Validate that this is a valid VM name and get the VM's resource group
                resourcegroup = validatetagvms(compute_client, taglist, az_vm_list, VMName)


                # If no resource group found, then that's a problem. we need to fail this record
                if (resourcegroup != ''):

                    print('Resource group (tageachvm): ', resourcegroup)
                    if (resourcegroup == ''):
                        updatelog('ERROR: empty resource group name in tageachvm()')

                    updatelog('Resource group for ', VMName, ' is ', resourcegroup)

                    # Tag this VM with this record
                    tagyoureit(credentials, subscription_id, compute_client, migrated_from, migrate_project, region, VMName, resourcegroup, tagline)

                else:
                    updatelog('ERROR: no resource group was found for this VM! (', VMName, ')')
                    writetosuccessfaillog(VMName, 'FAILED')

        print('-----------------------------------')
        counter += 1



# Search Azure to verify that there is a machine by this name, if there is, get the associated resource group
def validatetagvms(compute_client, taglist, az_vm_list, VMName):

    print('--- In validatetagvms --- ')

    if (VMName == ''):
        updatelog('ERROR: in validatetagvms() NULL VMName')

    print('VMName: ', VMName)

    vm_list = compute_client.virtual_machines.list_all()

    resourcegroup = ''
    i = 0
    for vm in vm_list:
        array = vm.id.split("/")
        resource_group = array[4]
        vm_name = array[-1]
        statuses = compute_client.virtual_machines.instance_view(resource_group, vm_name).statuses
        status = len(statuses) >= 2 and statuses[1]

        if (VMName == vm_name):
            resourcegroup = resource_group
            print(vm_name, 'in resource group', resourcegroup, 'Type:', type(resourcegroup))
            break

    if (resourcegroup == ''):
        updatelog('ERROR: ', VMName, ' resource group not found')


    print('--- Exit validatetagvms --- ')

    return(resourcegroup)


# Iterate through all VMs....
def getallazvms(compute_client, target_vm_list):

    vm_list = compute_client.virtual_machines.list_all()
    az_vm_list = []

    i = 0
    for vm in vm_list:
        array = vm.id.split("/")
        resource_group = array[4]
        vm_name = array[-1]
        statuses = compute_client.virtual_machines.instance_view(resource_group, vm_name).statuses
        status = len(statuses) >= 2 and statuses[1]

        #print(vm_name)


        if (vm_name.upper() in (name.upper() for name in target_vm_list)):
            print('Adding ', vm_name, ' to list')
            az_vm_list.append(vm_name)
        else:
            print('VM not in list ', vm_name)


    return az_vm_list


# Reads file and loads tags into memory
def loadrecordsfromfile(inputfilename, outputlist):

    # Open file
    inputfile = open(inputfilename, 'r')

    # Read each line in and process it
    count = 0
    while True:
        count += 1

        # Read next line from file
        line = inputfile.readline()

        # Break when we run out of data (empty line)
        if not line:
            break

        # Make it json
        data = json.loads(line)

        #print('Line: ', count, ' ', data, end='')

        outputlist.append(data)

        # Debug
        #break

    # Close the file
    inputfile.close()



# Call main
if __name__ == '__main__':
    main()
