import { supabase } from './supabase';

const API_PORT = 49232;

export const getApiHost = (): string => {
  if (typeof window === 'undefined') {
    return '127.0.0.1';
  }

  return window.location.hostname || '127.0.0.1';
};

export const getApiBaseUrl = (): string => {
  const configuredUrl = import.meta.env.VITE_API_URL;
  if (configuredUrl) {
    return configuredUrl.replace(/\/+$/, '');
  }

  // In production deployment (e.g. DigitalOcean), default to same-origin /api reverse proxy
  if (
    typeof window !== 'undefined' &&
    window.location.hostname !== 'localhost' &&
    window.location.hostname !== '127.0.0.1'
  ) {
    return '/api';
  }

  return `http://${getApiHost()}:${API_PORT}`;
};

/**
 * Authorization header carrying the current Supabase access token, if signed in.
 * The Flask API verifies it only when AUTH_ENABLED=true, so sending it always is
 * safe and forward-compatible.
 */
export const getAuthHeaders = async (): Promise<Record<string, string>> => {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
};
