import React, { useCallback, useEffect, useState } from 'react';
import { toast } from 'react-hot-toast';
import { supabase } from '../../lib/supabase';
import { useAuthStore } from '../../stores/authStore';
import type { ExtendedProfile } from '../../types';
import Button from '../ui/Button';

const inputClasses =
  'mt-2 block w-full rounded-[24px] border border-emerald-100 bg-white px-4 py-3 text-slate-900 shadow-sm outline-none transition focus:border-emerald-300 focus:ring-2 focus:ring-emerald-200';

const ProfileForm: React.FC = () => {
  const { user } = useAuthStore();
  const [loading, setLoading] = useState(false);
  const [profile, setProfile] = useState<ExtendedProfile>({
    id: user?.id || '',
    full_name: '',
    date_of_birth: '',
    gender: null,
    phone_number: '',
    created_at: '',
    updated_at: '',
  });

  const loadProfile = useCallback(async () => {
    try {
      setLoading(true);
      const { data, error } = await supabase.from('extended_profiles').select('*').eq('id', user?.id).single();

      if (error) throw error;
      if (data) setProfile(data);
    } catch (error) {
      console.error('Error loading profile:', error);
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    if (user) {
      void loadProfile();
    }
  }, [user, loadProfile]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();

    try {
      setLoading(true);
      const { error } = await supabase.from('extended_profiles').upsert({
        id: user?.id,
        full_name: profile.full_name,
        date_of_birth: profile.date_of_birth,
        gender: profile.gender,
        phone_number: profile.phone_number,
        updated_at: new Date().toISOString(),
      });

      if (error) throw error;
      toast.success('Profile saved.');
    } catch (error) {
      console.error('Error updating profile:', error);
      toast.error('Could not save your profile. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="grid gap-4 md:grid-cols-2">
      <div className="md:col-span-2">
        <label className="text-sm font-medium text-slate-700">Full name</label>
        <input
          type="text"
          value={profile.full_name || ''}
          onChange={(event) => setProfile({ ...profile, full_name: event.target.value })}
          className={inputClasses}
        />
      </div>

      <div>
        <label className="text-sm font-medium text-slate-700">Date of birth</label>
        <input
          type="date"
          value={profile.date_of_birth || ''}
          onChange={(event) => setProfile({ ...profile, date_of_birth: event.target.value })}
          className={inputClasses}
        />
      </div>

      <div>
        <label className="text-sm font-medium text-slate-700">Gender</label>
        <select
          value={profile.gender || ''}
          onChange={(event) => setProfile({ ...profile, gender: event.target.value as ExtendedProfile['gender'] })}
          className={inputClasses}
        >
          <option value="">Select gender</option>
          <option value="Male">Male</option>
          <option value="Female">Female</option>
          <option value="Other">Other</option>
        </select>
      </div>

      <div className="md:col-span-2">
        <label className="text-sm font-medium text-slate-700">Phone number</label>
        <input
          type="tel"
          value={profile.phone_number || ''}
          onChange={(event) => setProfile({ ...profile, phone_number: event.target.value })}
          className={inputClasses}
        />
      </div>

      <div className="md:col-span-2">
        <Button type="submit" disabled={loading}>
          {loading ? 'Saving profile...' : 'Save Cardios profile'}
        </Button>
      </div>
    </form>
  );
};

export default ProfileForm;
