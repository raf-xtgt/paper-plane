"use client";

import { useState } from 'react';
import { LeadGenService } from '@/app/services/leadGenService';

export default function LeadSearch() {
    const [district, setDistrict] = useState('');
    const [city, setCity] = useState('');
    const [industry, setIndustry] = useState('');
    const [submittedData, setSubmittedData] = useState<{
        district: string;
        city: string;
        industry: string;
    } | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsLoading(true);
        setError(null);

        try {
            // Prepare payload according to LeadGenRequest model
            const payload = {
                district: district,
                city: city,
                market: industry as "Student Recruitment" | "Medical Tourism"
            };

            // Call the lead generation service
            const response = await LeadGenService.triggerLeadGeneration(payload);

            // Display the submitted data and response
            setSubmittedData({
                district,
                city,
                industry
            });

            console.log('Lead Generation Response:', response);
            console.log('Lead Generation Data:', payload);

        } catch (err) {
            setError(err instanceof Error ? err.message : 'An error occurred');
            console.error('Lead Generation Error:', err);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="p-6 bg-white rounded-lg shadow-md">
            <h2 className="text-2xl font-bold mb-6 text-gray-800">Lead Search</h2>

            <form onSubmit={handleSubmit} className="space-y-4">
                {/* Form Fields in Same Row */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {/* District Input */}
                    <div>
                        <label htmlFor="district" className="block text-sm font-medium text-gray-700 mb-1">
                            District
                        </label>
                        <input
                            type="text"
                            id="district"
                            value={district}
                            onChange={(e) => setDistrict(e.target.value)}
                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                            placeholder="Enter district"
                            required
                        />
                    </div>

                    {/* City Input */}
                    <div>
                        <label htmlFor="city" className="block text-sm font-medium text-gray-700 mb-1">
                            City
                        </label>
                        <input
                            type="text"
                            id="city"
                            value={city}
                            onChange={(e) => setCity(e.target.value)}
                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                            placeholder="Enter city"
                            required
                        />
                    </div>

                    {/* Industry Dropdown */}
                    <div>
                        <label htmlFor="industry" className="block text-sm font-medium text-gray-700 mb-1">
                            Industry
                        </label>
                        <select
                            id="industry"
                            value={industry}
                            onChange={(e) => setIndustry(e.target.value)}
                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                            required
                        >
                            <option value="">Select an industry</option>
                            <option value="Medical Tourism">Medical Tourism</option>
                            <option value="Student Recruitment">Student Recruitment</option>
                        </select>
                    </div>
                </div>

                {/* Submit Button */}
                <button
                    type="submit"
                    disabled={isLoading}
                    className={`bg-blue-600 text-white py-2 px-6 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors font-medium ${
                        isLoading ? 'opacity-50 cursor-not-allowed' : ''
                    }`}
                >
                    {isLoading ? 'Processing...' : 'Start Lead Generation AI Pipeline'}
                </button>
            </form>

            {/* Error Display */}
            {error && (
                <div className="mt-4 p-4 bg-red-100 border border-red-400 text-red-700 rounded-md">
                    <strong>Error:</strong> {error}
                </div>
            )}

            {/* Display Submitted Data */}
            {submittedData && (
                <div className="mt-6 p-4 bg-gray-100 rounded-md">
                    <h3 className="text-lg font-semibold mb-2 text-gray-800">Submitted Data:</h3>
                    <div className="space-y-1 text-sm text-gray-600">
                        <p><strong>District:</strong> {submittedData.district}</p>
                        <p><strong>City:</strong> {submittedData.city}</p>
                        <p><strong>Industry:</strong> {submittedData.industry}</p>
                    </div>
                </div>
            )}
        </div>
    );
}