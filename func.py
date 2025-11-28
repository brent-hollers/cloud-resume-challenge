import json
import boto3

# Initialize the Database Connection
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('cloud-resume-challenge')

def lambda_handler(event, context):
    # 1. Get the current visitor count
    response = table.get_item(Key={'ID': 'visitors'})
    
    # (If the table is empty for some reason, default to 0)
    if 'Item' in response:
        views = response['Item']['visitors']
    else:
        views = 0
    
    # 2. Increment the count
    views = views + 1
    print(f"New visitor count: {views}")
    
    # 3. Save the new count back to DynamoDB
    table.put_item(Item={
            'ID': 'visitors',
            'visitors': views
    })
    
    # 4. Return the result to the API (with CORS headers!)
    return {
        'statusCode': 200,
        'headers': {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
        },
        'body': json.dumps(str(views))
    }