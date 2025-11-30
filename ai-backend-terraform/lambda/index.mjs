import { BedrockRuntimeClient, InvokeModelWithResponseStreamCommand } from "@aws-sdk/client-bedrock-runtime";
import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { DynamoDBDocumentClient, GetCommand, UpdateCommand } from "@aws-sdk/lib-dynamodb";
import awslambda from "aws-lambda";

const bedrock = new BedrockRuntimeClient({ region: process.env.AWS_REGION || 'us-east-1' });
const dynamodb = DynamoDBDocumentClient.from(new DynamoDBClient({}));

async function checkRateLimit(clientId) {
    try {
        const result = await dynamodb.send(new GetCommand({
            TableName: process.env.DYNAMODB_TABLE,
            Key: { client_id: clientId }
        }));
        
        if (result.Item && result.Item.count >= parseInt(process.env.RATE_LIMIT_PER_HOUR)) {
            return false;
        }
        return true;
    } catch (error) {
        return true;
    }
}

async function incrementUsage(clientId) {
    const ttl = Math.floor(Date.now() / 1000) + 3600;
    await dynamodb.send(new UpdateCommand({
        TableName: process.env.DYNAMODB_TABLE,
        Key: { client_id: clientId },
        UpdateExpression: 'ADD #count :inc SET #ttl = :ttl',
        ExpressionAttributeNames: { '#count': 'count', '#ttl': 'ttl' },
        ExpressionAttributeValues: { ':inc': 1, ':ttl': ttl }
    }));
}

export const handler = awslambda.streamifyResponse(
    async (event, responseStream, context) => {
        const clientId = event.requestContext?.http?.sourceIp || 'unknown';
        
        // Check rate limit
        if (!await checkRateLimit(clientId)) {
            const metadata = {
                statusCode: 429,
                headers: { 'Content-Type': 'application/json' }
            };
            responseStream = awslambda.HttpResponseStream.from(responseStream, metadata);
            responseStream.write(JSON.stringify({ error: 'Rate limit exceeded' }));
            responseStream.end();
            return;
        }
        
        // Parse request
        let body;
        try {
            body = JSON.parse(event.body || '{}');
        } catch (error) {
            const metadata = {
                statusCode: 400,
                headers: { 'Content-Type': 'application/json' }
            };
            responseStream = awslambda.HttpResponseStream.from(responseStream, metadata);
            responseStream.write(JSON.stringify({ error: 'Invalid request' }));
            responseStream.end();
            return;
        }
        
        await incrementUsage(clientId);
        
        // Setup streaming response
        const metadata = {
            statusCode: 200,
            headers: {
                'Content-Type': 'text/plain',
                'X-Content-Type-Options': 'nosniff'
            }
        };
        responseStream = awslambda.HttpResponseStream.from(responseStream, metadata);
        
        // Call Bedrock with streaming
        try {
            const command = new InvokeModelWithResponseStreamCommand({
                modelId: process.env.BEDROCK_MODEL_ID,
                body: JSON.stringify({
                    anthropic_version: "bedrock-2023-05-31",
                    max_tokens: body.max_tokens || 1024,
                    messages: body.messages || []
                })
            });
            
            const response = await bedrock.send(command);
            
            for await (const event of response.body) {
                if (event.chunk) {
                    const chunk = JSON.parse(new TextDecoder().decode(event.chunk.bytes));
                    if (chunk.type === 'content_block_delta' && chunk.delta?.text) {
                        responseStream.write(chunk.delta.text);
                    }
                }
            }
            
            responseStream.end();
        } catch (error) {
            responseStream.write(JSON.stringify({ error: error.message }));
            responseStream.end();
        }
    }
);
