/*
  # Enhanced User Profiles and Predictions

  1. New Tables
    - `extended_profiles`
      - Additional user information
      - Links to auth.users
    - `predictions`
      - Stores prediction history
      - Links to user profiles

  2. Security
    - Enable RLS on both tables
    - Add policies for user data access
*/

-- Extended profile information
CREATE TABLE IF NOT EXISTS extended_profiles (
  id uuid PRIMARY KEY REFERENCES auth.users ON DELETE CASCADE,
  full_name text,
  date_of_birth date,
  gender text CHECK (gender IN ('Male', 'Female', 'Other')),
  phone_number text,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- Prediction history
CREATE TABLE IF NOT EXISTS predictions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid REFERENCES auth.users ON DELETE CASCADE NOT NULL,
  prediction_result boolean NOT NULL,
  prediction_date timestamptz DEFAULT now(),
  bmi numeric,
  smoking boolean,
  alcohol_drinking boolean,
  stroke boolean,
  physical_health int,
  mental_health int,
  diff_walking boolean,
  sex text,
  age_category text,
  race text,
  diabetic boolean,
  physical_activity boolean,
  gen_health text,
  sleep_time numeric,
  asthma boolean,
  kidney_disease boolean,
  skin_cancer boolean
);

-- Enable RLS
ALTER TABLE extended_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE predictions ENABLE ROW LEVEL SECURITY;

-- Policies for extended_profiles
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

-- Policies for predictions
CREATE POLICY "Users can view own predictions"
  ON predictions FOR SELECT
  TO authenticated
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own predictions"
  ON predictions FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = user_id);