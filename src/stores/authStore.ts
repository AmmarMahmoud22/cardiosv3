import { create } from 'zustand';
import { supabase } from '../lib/supabase';
import type { User } from '@supabase/supabase-js';
import type { UserRole } from '../types';
import { getUserRole } from '../utils/roleUtils';

interface AuthState {
  user: User | null;
  role: UserRole | null;
  loading: boolean;
  roleLoading: boolean;
  setUser: (user: User | null) => void;
  refreshRole: () => Promise<UserRole | null>;
  signUp: (email: string, password: string) => Promise<void>;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  role: null,
  loading: true,
  roleLoading: false,
  
  setUser: (user) => {
    set({ user, loading: false, role: null, roleLoading: !!user });
    if (!user) return;
    void getUserRole(user.id).then((role) => {
      if (get().user?.id !== user.id) return;
      set({ role, roleLoading: false });
    }).catch((error) => {
      console.error('Role loading failed:', error);
      if (get().user?.id !== user.id) return;
      set({ role: 'patient', roleLoading: false });
    });
  },

  refreshRole: async () => {
    const user = get().user;
    if (!user) {
      set({ role: null, roleLoading: false });
      return null;
    }
    set({ roleLoading: true });
    const role = await getUserRole(user.id);
    if (get().user?.id === user.id) {
      set({ role, roleLoading: false });
    }
    return role;
  },
  
  signUp: async (email: string, password: string) => {
    const { data, error } = await supabase.auth.signUp({ email, password });
    if (error) throw error;

    // The profile row and the default 'patient' role are created server-side by the
    // `on_auth_user_created` trigger (handle_new_user, SECURITY DEFINER). That is
    // robust to the email-confirmation flow, where no client session exists yet
    // and a client-side insert would be blocked by RLS. When confirmation is off
    // a session is returned immediately, so reflect the signed-in user.
    if (data.session && data.user) {
      get().setUser(data.user);
    }
  },
  
  signIn: async (email: string, password: string) => {
    const { error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });
    if (error) throw error;
  },
  
  signOut: async () => {
    try {
      const { error } = await supabase.auth.signOut();
      if (error) throw error;
    } catch (error) {
      console.error('Sign out error:', error);
    } finally {
      // Always clear the user state, even if there's an error
      set({ user: null, role: null, loading: false, roleLoading: false });
    }
  },
}));
