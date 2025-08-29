import axios from 'axios';

const axiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'https://shift-app-backend.onrender.com/',
});

// Request interceptor to add the auth token header
axiosInstance.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor to handle 401 errors
axiosInstance.interceptors.response.use(
  (response) => {
    // If the request was successful, just return the response
    return response;
  },
  (error) => {
    // If the error is a 401 Unauthorized
    if (error.response && error.response.status === 401) {
      // Remove the invalid token from storage
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      
      // Redirect to the login page
      // Using window.location.href to force a full page reload, which clears any component state.
      window.location.href = '/login';
    }
    
    // For other errors, just pass them along
    return Promise.reject(error);
  }
);

export default axiosInstance;
