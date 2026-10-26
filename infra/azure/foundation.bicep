targetScope = 'resourceGroup'

@description('Região escolhida e autorizada pelo operador; deve coincidir com a do resource group.')
param location string = resourceGroup().location

@description('Repositório GitHub proprietário no formato owner/repo.')
param repository string

var suffix = uniqueString(resourceGroup().id)
var tags = {
  project: 'CloudCost'
  repository: repository
  managedBy: 'cloudcost-bootstrap'
}

resource registry 'Microsoft.ContainerRegistry/registries@2025-04-01' = {
  name: 'cloudcost${suffix}'
  location: location
  tags: tags
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
    anonymousPullEnabled: false
    // Basic tem endpoint público autenticado, não Private Link nem pull anônimo.
    publicNetworkAccess: 'Enabled'
    policies: {
      azureADAuthenticationAsArmPolicy: {
        status: 'enabled'
      }
    }
  }
}

resource pullIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = {
  name: 'cloudcost-pull-${suffix}'
  location: location
  tags: tags
}

var acrPullRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
resource registryPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, pullIdentity.id, acrPullRole)
  scope: registry
  properties: {
    roleDefinitionId: acrPullRole
    principalId: pullIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    description: 'Somente pull das imagens deste ACR pela identidade do CloudCost.'
  }
}

resource environment 'Microsoft.App/managedEnvironments@2025-07-01' = {
  name: 'cloudcost-env-${suffix}'
  location: location
  tags: tags
  properties: {
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
    zoneRedundant: false
  }
}

// A fundação não cria app nem usa imagem pública de exemplo.
output registryName string = registry.name
output registryId string = registry.id
output registryLoginServer string = registry.properties.loginServer
output environmentName string = environment.name
output pullIdentityName string = pullIdentity.name
output containerAppName string = 'cloudcost-app-${suffix}'
output location string = location
