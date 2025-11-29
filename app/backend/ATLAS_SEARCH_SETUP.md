# MongoDB Atlas Search Index Setup

This guide explains how to create the Atlas Search index for location autocomplete functionality.

## Prerequisites

- MongoDB Atlas cluster
- Access to Atlas UI or Admin API
- Database: `geofence`
- Collection: `locations`

## Step 1: Create the Search Index via Atlas UI

1. **Log in to MongoDB Atlas**
   - Go to https://cloud.mongodb.com
   - Select your cluster

2. **Navigate to Search**
   - Click on **"Search"** in the left sidebar
   - Click **"Create Search Index"**

3. **Configure the Index**
   - Select **"JSON Editor"** (not the visual editor)
   - Choose:
     - **Database**: `geofence`
     - **Collection**: `locations`
   - **Index Name**: `default` (or use the default index name)

4. **Paste the Configuration**
   Copy the contents from `atlas_search_index.json`:

```json
{
  "mappings": {
    "dynamic": false,
    "fields": {
      "name": [
        {
          "type": "autocomplete",
          "tokenization": "edgeGram",
          "minGrams": 2,
          "maxGrams": 15,
          "foldDiacritics": false
        },
        {
          "type": "string"
        }
      ],
      "city": [
        {
          "type": "autocomplete",
          "tokenization": "edgeGram",
          "minGrams": 2,
          "maxGrams": 15,
          "foldDiacritics": false
        },
        {
          "type": "string"
        }
      ],
      "country": [
        {
          "type": "autocomplete",
          "tokenization": "edgeGram",
          "minGrams": 2,
          "maxGrams": 15,
          "foldDiacritics": false
        },
        {
          "type": "string"
        }
      ],
      "type": {
        "type": "string"
      }
    }
  }
}
```

5. **Create the Index**
   - Click **"Create Search Index"**
   - Wait for the index to build (this may take a few minutes depending on your data size)

## Step 2: Verify the Index

Once created, you should see the index in the Search list with status "Active".

## Step 3: Test the API

The backend API will automatically use Atlas Search when available. Test it:

```bash
curl "http://localhost:8000/api/locations?search=Shanghai"
```

## Index Configuration Details

- **Autocomplete fields**: `name`, `city`, `country`
- **Tokenization**: `edgeGram` - matches from the beginning of words
- **Min/Max Grams**: 2-15 characters for autocomplete suggestions
- **Fuzzy matching**: Enabled in the API code for typo tolerance
- **String fields**: Also indexed as regular string for full-text search

## Troubleshooting

### Index Not Found Error

If you get an error about the index not being found:
1. Verify the index name matches `default` in Atlas (or update the code to match your index name)
2. Check that the index status is "Active"
3. Update the `search_index_name` variable in `main.py` if you used a different name

### Fallback Behavior

The API automatically falls back to regex search if Atlas Search is not available, so the application will still work (just without autocomplete features).

## Alternative: Create via Atlas Admin API

You can also create the index programmatically using the Atlas Admin API:

```bash
curl --user "PUBLIC_KEY:PRIVATE_KEY" \
  --digest \
  --header "Content-Type: application/json" \
  --request POST \
  "https://cloud.mongodb.com/api/atlas/v1.0/groups/{GROUP_ID}/clusters/{CLUSTER_NAME}/fts/indexes?databaseName=geofence&collectionName=locations" \
  --data @atlas_search_index.json
```

Replace:
- `PUBLIC_KEY` and `PRIVATE_KEY` with your Atlas API keys
- `GROUP_ID` with your project/group ID
- `CLUSTER_NAME` with your cluster name

