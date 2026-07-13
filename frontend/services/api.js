export async function fetchAPI(endpoint, options = {}) {
  const defaultHeaders = {
    'Content-Type': 'application/json',
  };

  const config = {
    ...options,
    headers: {
      ...defaultHeaders,
      ...options.headers,
    },
  };

  try {
    const res = await fetch(`/api${endpoint}`, config);
    const data = await res.json();
    
    if (!res.ok) {
      throw new Error(data.detail || data.message || `API Error: ${res.status}`);
    }
    
    return data;
  } catch (error) {
    console.error(`[API Error] ${endpoint}:`, error);
    throw error;
  }
}
