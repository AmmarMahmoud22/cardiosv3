/*
  # Fix User Roles Policies

  1. Changes
    - Drop existing problematic policies
    - Create new policies with proper checks to avoid recursion
    - Add basic policy for inserting new user roles
  
  2. Security
    - Maintain row level security
    - Fix infinite recursion in admin policy
    - Ensure proper access control
*/

-- Drop existing policies to recreate them
DROP POLICY IF EXISTS "Users can view own role" ON user_roles;
DROP POLICY IF EXISTS "Admins can manage all roles" ON user_roles;

-- Create new, fixed policies
CREATE POLICY "Anyone can view roles"
  ON user_roles FOR SELECT
  TO authenticated
  USING (true);

CREATE POLICY "Users can insert their own role"
  ON user_roles FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = user_id AND role = 'user');

CREATE POLICY "Admins can update roles"
  ON user_roles FOR UPDATE
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM user_roles
      WHERE user_id = auth.uid()
      AND role = 'admin'
      AND NOT is_banned
    )
  );

CREATE POLICY "Admins can delete roles"
  ON user_roles FOR DELETE
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM user_roles
      WHERE user_id = auth.uid()
      AND role = 'admin'
      AND NOT is_banned
    )
  );