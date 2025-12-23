
"use client";

import { useState, useEffect } from 'react';
import { FaArrowLeft, FaEdit, FaTimes } from 'react-icons/fa';
import { useStateController } from '@/app/context/stateController';
import { MsgService } from '@/app/services/msgService';

export default function LeadView() {
  const { selectedLead, setIsLeadViewOpen } = useStateController();
  const [isEditing, setIsEditing] = useState(false);
  const [outreachMessage, setOutreachMessage] = useState('');

  // Initialize outreach message when selectedLead changes
  useEffect(() => {
    if (selectedLead) {
      const message = selectedLead.outreach_draft_message || 
        `Hi ${selectedLead.primary_contact || 'there'}, I see ${selectedLead.org_name || 'your organization'} has great A-Level results. I help students secure scholarships in the UK. Open to a chat?`;
      setOutreachMessage(message);
    }
  }, [selectedLead]);

  const handleBackToList = () => {
    setIsLeadViewOpen(false);
  };

  const handleRejectLead = () => {
    // Handle reject lead logic
    console.log('Rejecting lead:', selectedLead?.guid);
    setIsLeadViewOpen(false);
  };

  const handleApproveAndSend = async () => {
    try {
      // Prepare the payload with hardcoded phone number for now
      const payload = {
        to_number: "whatsapp:+8801326237828",
        message_body: outreachMessage
      };

      console.log('Approving and sending message for lead:', selectedLead?.guid);
      console.log('Payload:', payload);

      // Call the sendMessage service
      const response = await MsgService.sendMessage(payload);
      console.log('Message sent successfully:', response);
      
      // Optionally close the lead view or show success message
      // setIsLeadViewOpen(false);
    } catch (error) {
      console.error('Failed to send message:', error);
      // Handle error - could show a toast notification or error message
    }
  };

  const handleSendLater = () => {
    // Handle send later logic
    console.log('Scheduling message for later for lead:', selectedLead?.guid);
  };

  if (!selectedLead) {
    return (
      <div className="p-6 text-center text-gray-500">
        Select a lead to view details
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-gray-50">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 bg-white">
        <button
          onClick={handleBackToList}
          className="flex items-center gap-2 text-gray-600 hover:text-gray-800 mb-3"
        >
          <FaArrowLeft /> Back to List
        </button>
        <h1 className="text-xl font-bold text-gray-800">
          Lead: {selectedLead.org_name}
        </h1>
      </div>

      {/* Content */}
      <div className="flex-1 p-4 space-y-4 overflow-y-auto">
        {/* AI Research Summary */}
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <h2 className="font-bold text-lg mb-3 text-gray-800">AI Research Summary</h2>
          
          <div className="space-y-3">
            <div>
              <span className="font-medium text-gray-700">Decision Maker:</span>
              <span className="ml-2 text-gray-600">{selectedLead.primary_contact}</span>
            </div>
            
            <div>
              <span className="font-medium text-gray-700">Title:</span>
              <span className="ml-2 text-gray-600">Head of Guidance Counseling</span>
            </div>
            
            <div>
              <span className="font-medium text-gray-700">Contact:</span>
              <span className="ml-2 text-gray-600">
                {selectedLead.phone_numbers?.[0] || 'No phone available'} (Public)
              </span>
            </div>
            
            <div>
              <span className="font-medium text-gray-700">Key Fact:</span>
              <span className="ml-2 text-gray-600">
                "{selectedLead.key_facts?.[0] || `${selectedLead.org_name} has great A-Level results`}"
              </span>
            </div>
            
            <div>
              <span className="font-medium text-gray-700">Source:</span>
              <span className="ml-2 text-blue-600 underline">{selectedLead.website_url}</span>
            </div>
          </div>
        </div>

        {/* AI-Drafted Outreach Message */}
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-bold text-lg text-gray-800">AI-Drafted Outreach Message</h2>
            <button
              onClick={() => setIsEditing(!isEditing)}
              className="flex items-center gap-1 text-blue-600 hover:text-blue-800"
            >
              <FaEdit /> Edit
            </button>
          </div>
          
          {isEditing ? (
            <textarea
              value={outreachMessage}
              onChange={(e) => setOutreachMessage(e.target.value)}
              className="w-full h-32 p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none"
              placeholder="Edit your outreach message..."
            />
          ) : (
            <div className="p-3 bg-gray-50 rounded-lg border border-gray-200">
              <p className="text-gray-700 leading-relaxed">"{outreachMessage}"</p>
            </div>
          )}
        </div>
      </div>

      {/* Action Buttons */}
      <div className="p-4 border-t border-gray-200 bg-white">
        <div className="flex flex-col sm:flex-row gap-3">
          <button
            onClick={handleRejectLead}
            className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors font-medium"
          >
            Reject Lead
          </button>
          
          <div className="flex gap-3 flex-1">
            <button
              onClick={handleApproveAndSend}
              className="flex-1 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors font-medium"
            >
              Approve & Send
            </button>
        
          </div>
        </div>
      </div>
    </div>
  );
}