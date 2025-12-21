"use client";

import { useState, useEffect } from 'react';
import {FaSearch, FaFolderOpen, FaClock, FaCheckCircle, FaExclamationCircle } from 'react-icons/fa';
import { LeadGenService } from '@/app/services/leadGenService';
import { useUser } from '@/app/context/userContext';
import { useStateController } from '@/app/context/stateController';
import { PPLPartnerProfile } from '@/app/models/partnerLeadProfile';

export default function LeadListing() {
  const [leadProfiles, setLeadProfiles] = useState<PPLPartnerProfile[]>([]);
  const [selectedLeadProfile, setSelectedLeadProfile] = useState<PPLPartnerProfile>();
  const [search, setSearch] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const { user } = useUser();
  const { setCurrentSessionGuid } = useStateController();

  // Load leadProfiles on component mount
  useEffect(() => {
    const loadProfiles = async () => {
      if (user?.guid) {
        try {
          setLoading(true);
          const response = await LeadGenService.getGeneratedLeadProfiles();
          console.log("lead partner profile listing", response)
          if (response.error) {
            setError(response.error);
          } else {
            setLeadProfiles(response.data);
          }
        } catch (err) {
          setError('Failed to load leadProfiles');
          console.error(err);
        } finally {
          setLoading(false);
        }
      }
    };

    loadProfiles();
  }, [user?.guid]);



  return (
    <div className="bg-gray-50 rounded-xl p-4 h-full flex flex-col">
      <div className="h-full flex flex-col">
        {/* Loading Message */}
        {loading && (
          <div className="mb-3 p-3 bg-blue-50 border border-blue-200 rounded-lg flex items-center gap-2 text-blue-700">
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-700"></div>
            <span>Retrieving Leads...</span>
          </div>
        )}

        {/* Success Message */}
        {successMessage && (
          <div className="mb-3 p-3 bg-green-50 border border-green-200 rounded-lg flex items-center gap-2 text-green-700">
            <FaCheckCircle />
            <span>{successMessage}</span>
          </div>
        )}

        {/* Error Message */}
        {error && (
          <div className="mb-3 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-red-700">
            <FaExclamationCircle />
            <span>{error}</span>
          </div>
        )}

        {/* Channels Section (leadProfiles Dropdown) */}
        <div className="pb-4 border-b border-gray-200">
          <h2 className="font-bold text-lg mb-3 flex justify-between items-center text-gray-800">
            <span className="flex items-center gap-2">
              <FaFolderOpen className="text-indigo-600" /> Leads
            </span>



          </h2>

          {/* Search input */}
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <FaSearch className="text-gray-400" />
            </div>
            <input
              type="text"
              placeholder="Search leadProfiles..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            />
          </div>

          <ul className="mt-3 max-h-60 overflow-y-auto space-y-2">
            {leadProfiles.map((profile, index) => (
              <li
                key={index} // 🔹 incremental numeric key
                className={`p-3 rounded-lg cursor-pointer flex justify-between items-center relative transition-colors ${selectedLeadProfile?.guid === profile.guid
                  ? 'bg-indigo-100 border border-indigo-300'
                  : 'bg-white border border-gray-200 hover:bg-gray-50'
                  }`}
                onClick={() => {
                  setSelectedLeadProfile(profile); // 🔹 store selected Session
                }}
              >
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-gray-800 truncate">{profile.org_name}</div>
                  <div className="font-medium text-gray-800 truncate">{profile.primary_contact}</div>
                  <div className="font-medium text-gray-800 truncate">{profile.lead_phase}</div>
                  <div className="text-xs text-gray-500 mt-1 flex items-center gap-1">
                    <FaClock /> {new Date(profile.created_date).toLocaleDateString()}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>


      </div>

    </div>

  );
}