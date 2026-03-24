export function getApiBase() {
  return import.meta.env.VITE_API_BASE || 'http://localhost:8000';
}
