from fastapi import FastAPI, Request
from pydantic import BaseModel
import numpy as np
from scipy.stats import weibull_min
from scipy.optimize import curve_fit

app = FastAPI()

class DataPoint(BaseModel):
    time: float
    measure: float

class WeibullRecord(BaseModel):
    time: float
    forecast: float

@app.get("/")
def read_root():
    return {"message": "Hello World"}


@app.post("/weibull", response_model=list[WeibullRecord])
async def analyze_weibull2(request: Request):
    data = await request.json()
    # Use only the months with non-zero error counts (months 1-60)
    data_points = [DataPoint(**item) for item in data if item['measure'] != 0]

    # Prepare observed times and measures
    times_obs = np.array([dp.time for dp in data_points])
    measures_obs = np.array([dp.measure for dp in data_points])

    # Define a scaled Weibull PDF model: f(t) = A * (beta/eta) * (t/eta)^(beta-1) * exp[-(t/eta)^beta]
    def weibull_pdf(t, A, beta, eta):
        return A * (beta / eta) * (t / eta) ** (beta - 1) * np.exp(- (t / eta) ** beta)

    # Initial guess for A, beta, and eta
    p0 = [measures_obs.sum(), 2.0, np.mean(times_obs)]
    popt, _ = curve_fit(weibull_pdf, times_obs, measures_obs, p0=p0)
    A, beta, eta = popt

    # Forecast: extend the time points.
    forecast_horizon = len(data) - len(data_points) 
    max_time = times_obs.max()  # should be 60
    extended_time_points = np.arange(1, int(max_time + forecast_horizon) + 1)

    # Compute forecast error counts using the fitted scaled Weibull PDF.
    forecast_values = weibull_pdf(extended_time_points, A, beta, eta)

    # Optionally, compute the underlying (unscaled) Weibull CDF/PDF if needed.
    cdf_values = weibull_min.cdf(extended_time_points, beta, loc=0, scale=eta)
    pdf_values = weibull_min.pdf(extended_time_points, beta, loc=0, scale=eta)
    
    # Note: 'mean' and 'std' from weibull_min are for the probability distribution,
    # not for the scaled error counts. You might want to report the fitted parameters instead.
    final_data = [
        WeibullRecord(
            time=t,
            forecast=forecast, # or compute another measure if needed
        )
        for t, cdf, pdf, forecast in zip(extended_time_points, cdf_values, pdf_values, forecast_values)
    ]
    
    return final_data
    

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8888)