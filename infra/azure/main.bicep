targetScope = 'resourceGroup'

param location string = resourceGroup().location
param registryName string
param environmentName string
param pullIdentityName string
param containerAppName string

@description('Digest privado aprovado: sha256 seguido de 64 dígitos hexadecimais; validado pelo script de entrega.')
@minLength(71)
@maxLength(71)
param imageDigest string

@description('Commit da imagem aprovada, conservado também nas evidências da entrega.')
@minLength(40)
@maxLength(40)
param sourceRevision string

resource registry 'Microsoft.ContainerRegistry/registries@2025-04-01' existing = {
  name: registryName
}

resource environment 'Microsoft.App/managedEnvironments@2025-07-01' existing = {
  name: environmentName
}

resource pullIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' existing = {
  name: pullIdentityName
}

// Sem roleAssignments nesta etapa: a identidade OIDC não administra RBAC.
module app './app.bicep' = {
  name: 'cloudcost-app'
  params: {
    location: location
    name: containerAppName
    environmentId: environment.id
    pullIdentityId: pullIdentity.id
    registryServer: registry.properties.loginServer
    image: '${registry.properties.loginServer}/cloudcost@${imageDigest}'
    sourceRevision: sourceRevision
  }
}

output endpoint string = app.outputs.endpoint
output containerAppId string = app.outputs.id
output image string = '${registry.properties.loginServer}/cloudcost@${imageDigest}'
output revisionName string = app.outputs.revisionName
