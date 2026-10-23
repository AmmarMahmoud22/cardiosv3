-- Create predictions table
create table if not exists public.predictions (
  id uuid default uuid_generate_v4() primary key,
  user_id uuid references auth.users not null,
  prediction_data jsonb not null,
  prediction_result text not null,
  created_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Enable RLS
alter table public.predictions enable row level security;

-- Add policies
create policy "Users can read their own predictions"
  on predictions for select
  using (auth.uid() = user_id);

create policy "Users can insert their own predictions"
  on predictions for insert
  with check (auth.uid() = user_id);

-- Create indexes for better performance
create index if not exists predictions_user_id_idx on predictions(user_id);
create index if not exists predictions_created_at_idx on predictions(created_at desc);

-- Create stats view for easier querying
create or replace view public.user_stats as
select
  user_id,
  count(*) as total_predictions,
  sum(case when prediction_result like '%High%' then 1 else 0 end) as high_risk_predictions,
  sum(case when prediction_result like '%Low%' then 1 else 0 end) as low_risk_predictions,
  max(created_at) as last_prediction_date
from public.predictions
group by user_id;

-- Grant access to authenticated users
grant select, insert on public.predictions to authenticated;
grant select on public.user_stats to authenticated;
