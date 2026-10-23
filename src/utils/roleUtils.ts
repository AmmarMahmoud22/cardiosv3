import { supabase } from '../lib/supabase';
import type { UserRole } from '../types';

type RoleRow = {
  role: string | null;
  is_banned?: boolean | null;
};

const normalizeRole = (role: string | null | undefined): UserRole => {
  if (role === 'doctor' || role === 'admin') return role;
  return 'patient';
};

export const getUserRole = async (userId: string): Promise<UserRole> => {
  const { data, error } = await supabase
    .from('user_roles')
    .select('role, is_banned')
    .eq('user_id', userId)
    .maybeSingle();

  if (error) {
    console.error('Could not load user role:', error);
    return 'patient';
  }

  const row = data as RoleRow | null;
  if (row?.is_banned) return 'patient';
  return normalizeRole(row?.role);
};

export const isAdmin = async (userId: string): Promise<boolean> => {
  const { data, error } = await supabase.rpc('is_admin', { uid: userId });
  if (!error) return data === true;
  return (await getUserRole(userId)) === 'admin';
};

export const isDoctor = async (userId: string): Promise<boolean> => {
  const { data, error } = await supabase.rpc('is_doctor', { uid: userId });
  if (!error) return data === true;
  return (await getUserRole(userId)) === 'doctor';
};

export const getDefaultRouteForRole = (role: UserRole | null): string => {
  if (role === 'admin') return '/admin';
  if (role === 'doctor') return '/doctor';
  return '/profile';
};
