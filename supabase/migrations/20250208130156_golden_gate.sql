/*
  # Fix Profiles RLS Policies

  1. Changes
    - Drop existing RLS policies for profiles table
    - Add new policy to allow profile creation during signup
    - Add policy for users to view their own profile
    - Add policy for users to update their own profile

  2. Security
    - Maintain row-level security
    - Allow authenticated users to manage their own profiles
    - Allow profile creation during signup
*/

-- Drop existing policies
DROP POLICY IF EXISTS "Users can read own profile" ON profiles;
DROP POLICY IF EXISTS "Users can update own profile" ON profiles;

-- Create new policies
CREATE POLICY "Enable insert for authenticated users"
  ON profiles FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = id);

CREATE POLICY "Enable select for users based on user_id"
  ON profiles FOR SELECT
  TO authenticated
  USING (auth.uid() = id);

CREATE POLICY "Enable update for users based on user_id"
  ON profiles FOR UPDATE
  TO authenticated
  USING (auth.uid() = id)
  WITH CHECK (auth.uid() = id);

-- Create policy for service role to manage profiles
CREATE POLICY "Enable service role to manage all profiles"
  ON profiles
  TO service_role
  USING (true)
  WITH CHECK (true);