import React from 'react';
import { supabase } from '../../lib/supabase';
import type { UserListItem } from '../../types/admin';

type ProfileRow = {
  id: string;
  email: string | null;
  created_at: string;
};

type RoleRow = {
  user_id: string;
  role: string;
  is_banned: boolean;
};

const UserList: React.FC = () => {
  const [users, setUsers] = React.useState<UserListItem[]>([]);

  React.useEffect(() => {
    const fetchUsers = async () => {
      const [{ data: profiles, error: profilesError }, { data: roles, error: rolesError }] =
        await Promise.all([
          supabase
            .from('profiles')
            .select('id, email, created_at')
            .order('created_at', { ascending: false })
            .limit(10),
          supabase.from('user_roles').select('user_id, role, is_banned'),
        ]);

      if (profilesError || rolesError) {
        console.error('Error fetching admin users:', profilesError || rolesError);
        return;
      }

      const roleMap = new Map<string, RoleRow>(
        (roles || []).map((item) => [item.user_id, item as RoleRow])
      );

      const mergedUsers = ((profiles || []) as ProfileRow[]).map((profile) => {
        const roleData = roleMap.get(profile.id);
        return {
          id: profile.id,
          email: profile.email || 'No email',
          created_at: profile.created_at,
          last_sign_in: null,
          role: roleData?.role || 'patient',
          is_banned: roleData?.is_banned || false,
        };
      });

      setUsers(mergedUsers);
    };

    void fetchUsers();
  }, []);

  if (!users.length) {
    return (
      <div className="rounded-[24px] border border-dashed border-emerald-200 bg-emerald-50/60 px-4 py-4 text-sm text-slate-600">
        No users available yet.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-emerald-100">
        <thead>
          <tr className="text-left text-xs uppercase tracking-[0.18em] text-slate-500">
            <th className="px-4 py-3">Email</th>
            <th className="px-4 py-3">Role</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Joined</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-emerald-50">
          {users.map((user) => (
            <tr key={user.id}>
              <td className="px-4 py-4 text-sm text-slate-900">{user.email}</td>
              <td className="px-4 py-4">
                <span className="inline-flex rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-700">
                  {user.role}
                </span>
              </td>
              <td className="px-4 py-4">
                <span
                  className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] ${
                    user.is_banned
                      ? 'bg-red-100 text-red-700'
                      : 'bg-emerald-100 text-emerald-700'
                  }`}
                >
                  {user.is_banned ? 'Banned' : 'Active'}
                </span>
              </td>
              <td className="px-4 py-4 text-sm text-slate-500">
                {new Date(user.created_at).toLocaleDateString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default UserList;
