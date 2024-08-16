import os
import json
import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

SSM_DOCUMENT_NAME = ''
SERVER_NAME = ''

ssm = boto3.client('ssm')

COMMAND_RUN = 'run'
COMMAND_STATUS = 'status'
STATUS_FAILED = 'FAILED'
STATUS_SUCCESS = 'SUCCESS'
STATUS_IN_PROGRESS = 'IN PROGRESS'


class UnknownCommandException(Exception):
    pass


def set_environment_variables():
    global ssm, SSM_DOCUMENT_NAME, SERVER_NAME
    SSM_DOCUMENT_NAME = os.environ['SSM_DOCUMENT_NAME']
    SERVER_NAME = os.environ['SERVER_NAME']


def extract_parameter(event, parameter):
    try:
        return event[parameter]
    except KeyError:
        raise KeyError(f'Error processing event, parameter {parameter} not found')


def run_command(event):
    order_number = extract_parameter(event, 'orderNumber')
    response = ssm.send_command(
        Targets=[{'Key': 'tag:Name', 'Values': [SERVER_NAME]}],
        DocumentName=SSM_DOCUMENT_NAME,
        Parameters={'salesOrderNumber': [order_number]},
        CloudWatchOutputConfig={'CloudWatchOutputEnabled': True}
    )
    command_id = response.get('Command', {}).get('CommandId', '')
    return {'commandId': command_id, 'status': STATUS_IN_PROGRESS}


def check_command_status(event):
    command_id = extract_parameter(event, 'commandId')
    response = ssm.list_commands(CommandId=command_id)
    commands = response.get('Commands', {})
    if commands:
        command = commands[0]
        aws_status = command['Status']
        status = STATUS_FAILED
        if aws_status in ['Pending', 'InProgress']:
            status = STATUS_IN_PROGRESS
        elif aws_status in ['Success']:
            status = STATUS_SUCCESS
        return {'commandId': command_id, 'status': status}

    raise Exception('Command is not found.')


def lambda_handler(event, context):
    # Log the received event
    logger.info("Received event: %s", json.dumps(event, indent=2))
    set_environment_variables()
    command = extract_parameter(event, 'command')
    if command == COMMAND_RUN:
        return run_command(event)
    elif command == COMMAND_STATUS:
        return check_command_status(event)
    else:
        raise UnknownCommandException('Unknown command')
