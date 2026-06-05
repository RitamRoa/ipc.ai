import pandas as pd

def clean_column_names(df):
    """Helper to standardize columns for easier access."""
    return df

def get_crime_filter(df, crime, cat_col, subcat_col):
    """Robust helper to filter the dataframe by a given crime search string."""
    if not crime:
        return df, "Total Crimes"
        
    c_lower = crime.lower().strip()
    if c_lower in ['total ipc', 'total crime', 'total crimes', 'all crimes', 'crime', 'crimes', 'total']:
        filtered = df[df[cat_col].str.contains('Total Cognizable', case=False, na=False)]
        if filtered.empty:
            return df, "Total Crimes"
        return filtered, "Total Crimes"
        
    filtered = df[df[subcat_col].str.contains(crime, case=False, na=False) | 
                  df[cat_col].str.contains(crime, case=False, na=False)]
    return filtered, crime.title()

def execute_plan(df: pd.DataFrame, plan: dict) -> dict:
    """
    Executes the structured JSON query plan against the Pandas dataframe.
    Returns a dictionary with 'answer' (string), 'data' (DataFrame or series/list), and 'computation' (string).
    """
    intent = plan.get('intent')
    
    if intent == 'out_of_scope':
        return {
            "answer": "This question cannot be answered from the IPC crime dataset.",
            "data": None,
            "computation": [
                "Identified query as out-of-scope based on intents.",
                "Blocked execution to prevent hallucinations."
            ]
        }
        
    if intent in ['rate_limited', 'api_error', 'invalid_json', 'error']:
        return {
            "answer": f"Planner failure: {intent}.",
            "data": None,
            "computation": ["Encountered a planner failure.", plan.get("message")]
        }

    # Common fields in the dataset
    state_col = 'State'
    cat_col = 'Crime head ipc ( indian penal code ) category'
    subcat_col = 'Crime head ipc ( indian penal code ) sub-category'
    incidents_col = 'Incidence of ipc ( indian penal code ) crimes'
    victims_col = 'Victims of ipc ( indian penal code ) crimes'
    rate_col = 'Ipc ( indian penal code ) crime rate'

    try:
        if intent == 'top_state':
            crime = plan.get('crime', '')
            metric = plan.get('metric', 'incidents')
            target_col = incidents_col if metric == 'incidents' else (rate_col if metric == 'rate' else victims_col)
            
            filtered, crime_name = get_crime_filter(df, crime, cat_col, subcat_col)
            
            if filtered.empty:
                return {
                    "answer": f"I don't have data specifically for '{crime_name}'. Try asking about categories like 'Murder', 'Kidnapping', 'Robbery', or 'Total Cognizable Crimes'.",
                    "data": None, 
                    "computation": ["Filtered dataframe is empty."]
                }
                
            grouped = filtered.groupby(state_col)[target_col].sum().reset_index()
            top = grouped.sort_values(by=target_col, ascending=False).iloc[0]
            
            return {
                "answer": f"The state with the highest {metric} for {crime_name} is {top[state_col]} with {int(top[target_col])}.",
                "data": grouped.nlargest(10, target_col),
                "computation": [
                    f"Filtered rows containing crime '{crime_name}'",
                    f"Grouped data by State",
                    f"Summed '{target_col}' counts",
                    f"Sorted descending",
                    f"Selected highest value"
                ]
            }

        elif intent == 'victims_analysis':
            crime = plan.get('crime', '')
            filtered, crime_name = get_crime_filter(df, crime, cat_col, subcat_col)
            
            if filtered.empty:
                return {
                    "answer": f"I don't have data specifically for '{crime_name}'. Try asking about categories like 'Murder', 'Kidnapping', 'Robbery', or 'Total Cognizable Crimes'.",
                    "data": None, 
                    "computation": ["Filtered dataframe is empty."]
                }
                
            grouped = filtered.groupby(state_col)[victims_col].sum().reset_index()
            top = grouped.sort_values(by=victims_col, ascending=False).iloc[0]
            
            return {
                "answer": f"For {crime_name}, the maximum victims were in {top[state_col]} ({int(top[victims_col])} victims).",
                "data": grouped.nlargest(10, victims_col),
                "computation": [
                    f"Filtered rows containing crime '{crime_name}'",
                    f"Grouped data by State",
                    f"Summed victim counts",
                    f"Sorted descending",
                    f"Selected highest value"
                ]
            }

        elif intent == 'crime_rate_ranking':
            crime = plan.get('crime', '')
            filtered, crime_name = get_crime_filter(df, crime, cat_col, subcat_col)
            
            if filtered.empty:
                return {
                    "answer": f"I don't have data specifically for '{crime_name}'.",
                    "data": None, 
                    "computation": ["Filtered dataframe is empty."]
                }
                
            grouped = filtered.groupby(state_col)[rate_col].sum().reset_index()
            top = grouped.sort_values(by=rate_col, ascending=False).iloc[0]
            
            return {
                "answer": f"The state with the highest crime rate for {crime_name} is {top[state_col]} with a rate of {round(top[rate_col], 2)}.",
                "data": grouped.nlargest(10, rate_col),
                "computation": [
                    f"Filtered rows containing crime '{crime_name}'",
                    f"Grouped data by State",
                    f"Summed crime rates",
                    f"Sorted descending",
                    f"Selected highest value"
                ]
            }

        elif intent == 'compare_states':
            crime = plan.get('crime', '')
            states = plan.get('states', [])
            
            filtered, crime_name = get_crime_filter(df, crime, cat_col, subcat_col)
            # Apply state filter
            filtered = filtered[filtered[state_col].str.title().isin([s.title() for s in states])]
                          
            grouped = filtered.groupby(state_col)[incidents_col].sum().reset_index()
            
            if grouped.empty:
                return {
                    "answer": f"I don't have enough data to compare these states for '{crime_name}'. Try asking about 'Murder', 'Kidnapping', or 'Robbery'.",
                    "data": None, 
                    "computation": ["Empty filter group."]
                }
                
            ans = " Comparing " + crime_name + ": " + ", ".join([f"{row[state_col]}: {int(row[incidents_col])}" for _, row in grouped.iterrows()])
            return {
                "answer": ans,
                "data": grouped,
                "computation": [
                    f"Filtered rows containing crime '{crime_name}'",
                    f"Filtered rows matching states: {states}",
                    f"Grouped by State",
                    f"Summed incident counts",
                    f"Compared values"
                ]
            }

        elif intent == 'category_ranking':
            metric = plan.get('metric', 'incidents')
            target_col = incidents_col if metric == 'incidents' else (rate_col if metric == 'rate' else victims_col)

            grouped = df.groupby(subcat_col)[target_col].sum().reset_index()
            grouped = grouped.sort_values(by=target_col, ascending=False)
            top = grouped.iloc[0]

            return {
                "answer": f"The crime category with the most {metric} is {top[subcat_col]} with {int(top[target_col])}.",
                "data": grouped.head(10),
                "computation": [
                    "Grouped data by crime sub-category",
                    f"Summed '{target_col}' values",
                    "Sorted descending",
                    "Selected the highest category"
                ]
            }
            
        else:
            return {
                "answer": "This query intent is supported but its execution handles are being refined.",
                "data": None,
                "computation": [f"Intent mapped: {intent}"]
            }
            
    except Exception as e:
        return {
            "answer": f"Error executing query: {str(e)}",
            "data": None,
            "computation": ["Error during pandas operations."]
        }
