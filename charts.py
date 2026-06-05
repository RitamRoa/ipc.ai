import plotly.express as px

def create_chart(plan: dict, execution_result: dict):
    """
    Dynamically generates Plotly visualizations based on the intent and result data.
    """
    data = execution_result.get('data')
    if data is None or data.empty:
        return None

    intent = plan.get('intent')
    crime = plan.get('crime', 'Crime')
    
    if intent in ['top_state', 'victims_analysis', 'crime_rate_ranking']:
        col_x = data.columns[0] # Usually State
        col_y = data.columns[1] # Metric
        fig = px.bar(
            data, 
            x=col_x, 
            y=col_y, 
            title=f"Top States for {crime}",
            labels={col_y: col_y.split('(')[0].strip(), col_x: "State"},
            color=col_y,
            color_continuous_scale="Reds"
        )
        return fig
        
    elif intent == 'compare_states':
        col_x = data.columns[0]
        col_y = data.columns[1]
        fig = px.bar(
            data, 
            x=col_x, 
            y=col_y, 
            title=f"Comparison of {crime}",
            color=col_x,
            text=col_y
        )
        fig.update_traces(textposition='outside')
        return fig

    return None