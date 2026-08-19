import { useState } from 'react'
import ProjectList from './components/ProjectList'
import Workspace from './components/Workspace'

export default function App() {
  const [projectId, setProjectId] = useState<string | null>(null)

  if (projectId) {
    return <Workspace projectId={projectId} onBack={() => setProjectId(null)} />
  }
  return <ProjectList onOpen={(id) => setProjectId(id)} />
}
