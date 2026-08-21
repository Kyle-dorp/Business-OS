import React from 'react'
import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { Plus } from 'lucide-react'

export const TeamChatPage = () => {
  return (
    <div className="p-8">
      <div className="max-w-6xl">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Team Chat</h1>
            <p className="text-gray-500 mt-2">Communicate with your team in real-time</p>
          </div>
          <Button variant="primary" icon={<Plus className="w-5 h-5" />}>New Channel</Button>
        </div>

        <Card>
          <h2 className="text-xl font-bold text-gray-900 mb-4">Channels</h2>
          <div className="text-center py-12 text-gray-500">
            No channels yet. Create your first channel to get started.
          </div>
        </Card>
      </div>
    </div>
  )
}
