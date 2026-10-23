/*
  # Update extended profiles and predictions tables

  This migration ensures tables and policies exist, and adds any missing ones.
  Using IF NOT EXISTS to prevent duplicate errors.
*/

-- Drop existing policies if they exist
DO $$ 
BEGIN
    -- Extended profiles policies
    DROP POLICY IF EXISTS "Users can view own extended profile" ON extended_profiles;
    DROP POLICY IF EXISTS "Users can update own extended profile" ON extended_profiles;
    DROP POLICY IF EXISTS "Users can insert own extended profile" ON extended_profiles;
    
    -- Predictions policies
    DROP POLICY IF EXISTS "Users can view own predictions" ON predictions;
    DROP POLICY IF EXISTS "Users can insert own predictions" ON predictions;
END $$;

-- Recreate policies
CREATE POLICY "Users can view own extended profile"
  ON extended_profiles FOR SELECT
  TO authenticated
  USING (auth.uid() = id);

CREATE POLICY "Users can update own extended profile"
  ON extended_profiles FOR UPDATE
  TO authenticated
  USING (auth.uid() = id);

CREATE POLICY "Users can insert own extended profile"
  ON extended_profiles FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = id);

CREATE POLICY "Users can view own predictions"
  ON predictions FOR SELECT
  TO authenticated
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own predictions"
  ON predictions FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = user_id);