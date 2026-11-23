const OBJECT_KEY = 'drug_catalog.enc.json';

function corsHeaders() {
  return {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff'
  };
}

export default {
  async fetch(request, env) {
    const headers = corsHeaders();
    if (request.method === 'OPTIONS') {
      return new Response(null, {status: 204, headers});
    }
    if (request.method !== 'GET') {
      return new Response('Method not allowed', {status: 405, headers});
    }

    const object = await env.CATALOG_BUCKET.get(OBJECT_KEY);
    if (!object) {
      return new Response('Drug catalog has not been published yet.', {
        status: 404,
        headers
      });
    }

    headers['Content-Type'] = 'application/json; charset=utf-8';
    return new Response(object.body, {status: 200, headers});
  }
};
